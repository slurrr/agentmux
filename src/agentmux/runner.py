from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agentmux.config import STACK_ROOT, FlagValue, LoraSpec, ServiceSpec, StackSpec, resolve_stack
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


ASSET_FLAG_MAP = {
    "chat_template": "--chat-template",
    "tokenizer": "--tokenizer",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _venv_site_packages_dir() -> Path | None:
    lib_root = _repo_root() / ".venv" / "lib"
    if not lib_root.is_dir():
        return None
    candidates = sorted(lib_root.glob("python*/site-packages"))
    if not candidates:
        return None
    return candidates[-1]


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    site_packages = _venv_site_packages_dir()
    cuda_home: Path | None = None
    for candidate in (Path("/usr/local/cuda"), Path("/usr/local/cuda-13.2")):
        if candidate.is_dir():
            cuda_home = candidate
            break

    if cuda_home is not None:
        env.setdefault("CUDA_HOME", str(cuda_home))
        env.setdefault("CUDA_PATH", str(cuda_home))
        env.setdefault("CUDACXX", str(cuda_home / "bin" / "nvcc"))
        gcc14 = Path("/usr/bin/g++-14")
        if gcc14.is_file():
            env.setdefault("NVCC_CCBIN", str(gcc14))
        current_path = env.get("PATH", "")
        path_parts = [str(cuda_home / "bin")]
        if current_path:
            path_parts.extend(part for part in current_path.split(":") if part)
        deduped_path: list[str] = []
        seen_path: set[str] = set()
        for path in path_parts:
            if path and path not in seen_path:
                deduped_path.append(path)
                seen_path.add(path)
        env["PATH"] = ":".join(deduped_path)

    if site_packages is None:
        return env

    lib_dirs: list[str] = []

    torch_lib = site_packages / "torch" / "lib"
    if torch_lib.is_dir():
        lib_dirs.append(str(torch_lib))

    nvidia_root = site_packages / "nvidia"
    if nvidia_root.is_dir():
        for child in sorted(nvidia_root.iterdir()):
            lib_dir = child / "lib"
            if lib_dir.is_dir():
                lib_dirs.append(str(lib_dir))

    current = env.get("LD_LIBRARY_PATH", "")
    if current:
        lib_dirs.extend(part for part in current.split(":") if part)

    deduped: list[str] = []
    seen: set[str] = set()
    for path in lib_dirs:
        if path and path not in seen:
            deduped.append(path)
            seen.add(path)

    if deduped:
        env["LD_LIBRARY_PATH"] = ":".join(deduped)
    return env


def _apply_loras(command: list[str], loras: list[LoraSpec]) -> None:
    enabled = [lora for lora in loras if lora.enabled]
    if not enabled:
        return
    command.append("--enable-lora")
    for lora in enabled:
        command.extend(["--lora-modules", f"{lora.name}={lora.path}"])


def _apply_flag_map(
    command: list[str],
    args: dict[str, FlagValue],
    excluded_keys: set[str] | None = None,
) -> None:
    excluded = excluded_keys or set()
    for key, value in args.items():
        if key in excluded:
            continue
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                command.append(flag)
            continue
        command.extend([flag, str(value)])


def _apply_assets(command: list[str], service: ServiceSpec) -> set[str]:
    applied_keys: set[str] = set()
    for key, flag in ASSET_FLAG_MAP.items():
        value = service.assets.values.get(key)
        if value:
            command.extend([flag, value])
            applied_keys.add(key)
    return applied_keys


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
    asset_keys = _apply_assets(command, service)
    _apply_flag_map(command, service.args, excluded_keys=asset_keys)
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
        env = _runtime_env()
        env.update(stack.env)
        env.update(service.env)

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
    active = read_active(prune_stale=True)
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
