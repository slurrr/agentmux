from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agentmux.config import STACK_ROOT, LoraSpec, ServiceSpec, StackSpec, resolve_stack
from agentmux.runtime import (
    RuntimeService,
    RuntimeStack,
    next_log_path,
    pid_is_running,
    read_active,
    write_active,
)


@dataclass(frozen=True)
class ServiceLaunchPlan:
    stack: str
    service: str
    env: dict[str, str]
    command: list[str]
    port: int

    def shell_command(self) -> str:
        return shlex.join(self.command)


@dataclass(frozen=True)
class StackLaunchPlan:
    stack: StackSpec
    services: list[ServiceLaunchPlan]


def _apply_loras(command: list[str], loras: list[LoraSpec]) -> None:
    enabled = [lora for lora in loras if lora.enabled]
    if not enabled:
        return
    command.append("--enable-lora")
    for lora in enabled:
        command.extend(["--lora-modules", f"{lora.name}={lora.path}"])


def _build_vllm_command(service: ServiceSpec) -> list[str]:
    command = [
        "uv",
        "run",
        "vllm",
        "serve",
        service.model,
        "--host",
        service.host,
        "--port",
        str(service.port),
    ]
    if service.served_model_name:
        command.extend(["--served-model-name", service.served_model_name])
    if service.dtype:
        command.extend(["--dtype", service.dtype])
    if service.gpu_memory_utilization is not None:
        command.extend(["--gpu-memory-utilization", str(service.gpu_memory_utilization)])
    if service.max_model_len is not None:
        command.extend(["--max-model-len", str(service.max_model_len)])
    if service.max_num_seqs is not None:
        command.extend(["--max-num-seqs", str(service.max_num_seqs)])
    if service.tensor_parallel_size is not None:
        command.extend(["--tensor-parallel-size", str(service.tensor_parallel_size)])
    if service.attention_backend:
        command.extend(["--attention-backend", service.attention_backend])
    _apply_loras(command, service.loras)
    command.extend(service.extra_args)
    return command


def build_stack_plan(
    stack_name: str,
    root: Path = STACK_ROOT,
    include_archive: bool = True,
) -> StackLaunchPlan:
    load_dotenv(dotenv_path=Path(".env"))
    stack = resolve_stack(stack_name, root=root, include_archive=include_archive)

    services: list[ServiceLaunchPlan] = []
    for service_name, service in stack.services.items():
        env = os.environ.copy()
        env.update(stack.env)
        env.update(service.env)
        if service.api_key_env:
            api_key = os.environ.get(service.api_key_env)
            if api_key:
                env.setdefault("VLLM_API_KEY", api_key)

        if service.engine != "vllm":
            raise ValueError(f"Unsupported engine in v1: {service.engine}")

        services.append(
            ServiceLaunchPlan(
                stack=stack.name,
                service=service_name,
                env=env,
                command=_build_vllm_command(service),
                port=service.port,
            )
        )

    return StackLaunchPlan(stack=stack, services=services)


def launch_stack(stack_name: str, root: Path = STACK_ROOT) -> RuntimeStack:
    active = read_active()
    if active is not None and any(pid_is_running(service.pid) for service in active.services):
        raise RuntimeError(f"Active stack already running: {active.stack}")

    plan = build_stack_plan(stack_name, root=root)
    runtime_services: list[RuntimeService] = []

    for service in plan.services:
        log_path = next_log_path(plan.stack.name, service.service)
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                service.command,
                env=service.env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        runtime_services.append(
            RuntimeService(
                name=service.service,
                pid=process.pid,
                port=service.port,
                command=service.command,
                log_path=str(log_path),
                started_at=time.time(),
            )
        )

    runtime_stack = RuntimeStack(
        stack=plan.stack.name,
        track=plan.stack.track,
        path=str(plan.stack.path),
        services=runtime_services,
        started_at=time.time(),
    )
    write_active(runtime_stack)
    return runtime_stack
