from __future__ import annotations

import os
import shlex
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agentmux.config import (
    STACK_ROOT,
    FlagValue,
    LoraSpec,
    MemorySpec,
    ServiceSpec,
    StackSpec,
    resolve_stack,
)
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
class MemoryLaunchPlan:
    stack: str
    service: str
    env: dict[str, str]
    command: list[str]
    port: int
    host: str
    managed: bool

    def shell_command(self) -> str:
        return shlex.join(self.command)


@dataclass(frozen=True)
class StackLaunchPlan:
    stack: StackSpec
    services: list[ServiceLaunchPlan]
    memory: MemoryLaunchPlan | None


ASSET_FLAG_MAP = {
    "chat_template": "--chat-template",
    "tokenizer": "--tokenizer",
}

PRIMARY_STARTUP_TIMEOUT_SECONDS = 120.0
PRIMARY_STARTUP_POLL_SECONDS = 0.5
HINDSIGHT_STARTUP_POLL_SECONDS = 0.5
HINDSIGHT_START_RETRY_DELAY_SECONDS = 5.0
HINDSIGHT_START_MAX_ATTEMPTS = 4


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


def _display_host(host: str) -> str:
    return "127.0.0.1" if host == "0.0.0.0" else host


def _service_base_url(host: str, port: int) -> str:
    return f"http://{_display_host(host)}:{port}/v1"


def _port_is_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _vllm_models_ready(host: str, port: int) -> bool:
    url = f"{_service_base_url(host, port)}/models"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status < 400
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _hindsight_healthcheck(host: str, port: int) -> bool:
    for path in ("/health", "/"):
        url = f"http://{host}:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status < 400:
                    return True
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, ConnectionError):
            continue
    return False


def _build_memory_plan(stack: StackSpec, memory: MemorySpec, base_env: dict[str, str]) -> MemoryLaunchPlan:
    primary = stack.services[stack.primary_service]
    llm_model = primary.served_model_name or primary.model
    llm_base_url = _service_base_url(primary.host, primary.port)

    env = dict(base_env)
    env.update(
        {
            "HINDSIGHT_BIND_HOST": memory.host,
            "HINDSIGHT_BIND_PORT": str(memory.port),
            "HINDSIGHT_DATA_DIR": memory.data_dir,
            "HINDSIGHT_LLM_PROVIDER": "openai",
            "HINDSIGHT_LLM_MODEL": llm_model,
            "HINDSIGHT_LLM_API_KEY": env.get("HINDSIGHT_LLM_API_KEY", "dummy"),
            "HINDSIGHT_LLM_BASE_URL": llm_base_url,
        }
    )

    if _port_is_in_use(memory.host, memory.port):
        if _hindsight_healthcheck(memory.host, memory.port):
            return MemoryLaunchPlan(
                stack=stack.name,
                service="hindsight",
                env=env,
                command=["external-hindsight", f"http://{memory.host}:{memory.port}"],
                port=memory.port,
                host=memory.host,
                managed=False,
            )
        raise RuntimeError(
            f"stack.memory requested hindsight on {memory.host}:{memory.port}, "
            "but the port is already in use by another process"
        )

    command = ["uv", "run", "python", "scripts/hindsight_dev.py"]
    return MemoryLaunchPlan(
        stack=stack.name,
        service="hindsight",
        env=env,
        command=command,
        port=memory.port,
        host=memory.host,
        managed=True,
    )


def build_stack_plan(
    stack_name: str,
    root: Path = STACK_ROOT,
    include_archive: bool = True,
) -> StackLaunchPlan:
    load_dotenv(dotenv_path=Path(".env"))
    stack = resolve_stack(stack_name, root=root, include_archive=include_archive)

    services: list[ServiceLaunchPlan] = []
    base_env = _runtime_env()
    base_env.update(stack.env)

    for service_name, service in stack.services.items():
        env = dict(base_env)
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

    memory_plan = _build_memory_plan(stack, stack.memory, base_env) if stack.memory else None

    return StackLaunchPlan(stack=stack, services=services, memory=memory_plan)


def _terminate_runtime_services(services: list[RuntimeService]) -> None:
    for service in services:
        if not service.managed or service.pid <= 0:
            continue
        try:
            os.killpg(os.getpgid(service.pid), signal.SIGTERM)
        except ProcessLookupError:
            continue


def _drain_log_chunk(log_path: str, offset: int) -> tuple[int, str]:
    path = Path(log_path)
    if not path.exists():
        return offset, ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            chunk = handle.read()
            return handle.tell(), chunk
    except OSError:
        return offset, ""


def _wait_for_primary_ready(service: RuntimeService, host: str) -> bool:
    deadline = time.time() + PRIMARY_STARTUP_TIMEOUT_SECONDS
    offset = 0
    while time.time() < deadline:
        offset, chunk = _drain_log_chunk(service.log_path, offset)
        if chunk:
            print(chunk, end="", flush=True)
        if _vllm_models_ready(host, service.port):
            return True
        if not pid_is_running(service.pid):
            return False
        time.sleep(PRIMARY_STARTUP_POLL_SECONDS)
    offset, chunk = _drain_log_chunk(service.log_path, offset)
    if chunk:
        print(chunk, end="", flush=True)
    return _vllm_models_ready(host, service.port)


def _hindsight_startup_timeout_seconds() -> float | None:
    raw = os.environ.get("AGENTMUX_HINDSIGHT_STARTUP_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _wait_for_hindsight_ready(service: RuntimeService, host: str) -> bool:
    timeout = _hindsight_startup_timeout_seconds()
    deadline = (time.time() + timeout) if timeout is not None else None
    offset = 0
    while True:
        offset, chunk = _drain_log_chunk(service.log_path, offset)
        if chunk:
            print(chunk, end="", flush=True)
        if _hindsight_healthcheck(host, service.port):
            return True
        if not pid_is_running(service.pid):
            return False
        if deadline is not None and time.time() >= deadline:
            offset, chunk = _drain_log_chunk(service.log_path, offset)
            if chunk:
                print(chunk, end="", flush=True)
            return _hindsight_healthcheck(host, service.port)
        time.sleep(HINDSIGHT_STARTUP_POLL_SECONDS)


def launch_stack(stack_name: str, root: Path = STACK_ROOT) -> RuntimeStack:
    active = read_active(prune_stale=True)
    if active is not None and any(pid_is_running(service.pid) for service in active.services):
        raise RuntimeError(f"Active stack already running: {active.stack}")

    plan = build_stack_plan(stack_name, root=root)
    runtime_services: list[RuntimeService] = []

    try:
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

        if plan.memory is not None:
            primary_runtime = next(
                (service for service in runtime_services if service.name == plan.stack.primary_service),
                None,
            )
            if primary_runtime is not None:
                primary_spec = plan.stack.services[plan.stack.primary_service]
                if not _wait_for_primary_ready(primary_runtime, primary_spec.host):
                    raise RuntimeError(
                        "Primary service did not become ready before memory startup. "
                        f"See log: {primary_runtime.log_path}"
                    )

            if plan.memory.managed:
                memory_runtime: RuntimeService | None = None
                for attempt in range(1, HINDSIGHT_START_MAX_ATTEMPTS + 1):
                    log_path = next_log_path(plan.stack.name, plan.memory.service)
                    with log_path.open("ab") as log_handle:
                        process = subprocess.Popen(
                            plan.memory.command,
                            env=plan.memory.env,
                            stdout=log_handle,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    candidate = RuntimeService(
                        name=plan.memory.service,
                        pid=process.pid,
                        port=plan.memory.port,
                        command=plan.memory.command,
                        log_path=str(log_path),
                        started_at=time.time(),
                        managed=True,
                    )
                    if _wait_for_hindsight_ready(candidate, plan.memory.host):
                        memory_runtime = candidate
                        runtime_services.append(memory_runtime)
                        break
                    _terminate_runtime_services([candidate])
                    if attempt < HINDSIGHT_START_MAX_ATTEMPTS:
                        print(
                            f"warning: hindsight startup attempt {attempt}/{HINDSIGHT_START_MAX_ATTEMPTS} failed; retrying...",
                            flush=True,
                        )
                        time.sleep(HINDSIGHT_START_RETRY_DELAY_SECONDS)
                if memory_runtime is None:
                    raise RuntimeError(
                        "Hindsight sidecar failed to become ready after retries. "
                        f"See latest log: {log_path}"
                    )
            else:
                print(
                    f"Hindsight already up and running at http://{plan.memory.host}:{plan.memory.port}; reusing"
                )
                runtime_services.append(
                    RuntimeService(
                        name=plan.memory.service,
                        pid=0,
                        port=plan.memory.port,
                        command=plan.memory.command,
                        log_path="(external)",
                        started_at=time.time(),
                        managed=False,
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
    except Exception:
        _terminate_runtime_services(runtime_services)
        raise
