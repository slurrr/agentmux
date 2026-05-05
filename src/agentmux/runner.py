from __future__ import annotations

import os
import shlex
import signal
import sys
import socket
import subprocess
import time
import urllib.error
import urllib.request
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
    engine: str
    env: dict[str, str]
    command: list[str]
    port: int
    host: str
    managed: bool = True
    waits_for: str | None = None

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

PRIMARY_STARTUP_TIMEOUT_SECONDS = 120.0
PRIMARY_STARTUP_POLL_SECONDS = 0.5
HINDSIGHT_STARTUP_POLL_SECONDS = 0.5
HINDSIGHT_START_RETRY_DELAY_SECONDS = 5.0
HINDSIGHT_START_MAX_ATTEMPTS = 4


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_runtime_bin_dir(runtime_bin_dir: str | None) -> Path | None:
    if runtime_bin_dir is None:
        return None
    path = Path(runtime_bin_dir).expanduser()
    if not path.is_absolute():
        path = _repo_root() / path
    return path.resolve()


def _site_packages_dir_for_runtime(runtime_bin_dir: str | None) -> Path | None:
    if runtime_bin_dir is None:
        prefix = Path(sys.prefix)
    else:
        resolved_bin_dir = _resolve_runtime_bin_dir(runtime_bin_dir)
        if resolved_bin_dir is None:
            return None
        prefix = resolved_bin_dir.parent
    lib_root = prefix / "lib"
    if not lib_root.is_dir():
        return None
    candidates = sorted(lib_root.glob("python*/site-packages"))
    if not candidates:
        return None
    return candidates[-1]


def _without_repo_venv_paths(paths: list[str]) -> list[str]:
    legacy_bin = str(_repo_root() / ".venv" / "bin")
    legacy_lib = str(_repo_root() / ".venv" / "lib")
    cleaned: list[str] = []
    for path in paths:
        if not path:
            continue
        if path == legacy_bin or path.startswith(f"{legacy_lib}/") or path == legacy_lib:
            continue
        cleaned.append(path)
    return cleaned


def _runtime_env(runtime_bin_dir: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    resolved_bin_dir = _resolve_runtime_bin_dir(runtime_bin_dir)
    site_packages = _site_packages_dir_for_runtime(runtime_bin_dir)
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
        path_parts: list[str] = []
        if resolved_bin_dir is not None:
            path_parts.append(str(resolved_bin_dir))
        path_parts.append(str(cuda_home / "bin"))
        if current_path:
            path_parts.extend(_without_repo_venv_paths(current_path.split(":")))
        deduped_path: list[str] = []
        seen_path: set[str] = set()
        for path in path_parts:
            if path and path not in seen_path:
                deduped_path.append(path)
                seen_path.add(path)
        env["PATH"] = ":".join(deduped_path)

    if resolved_bin_dir is not None:
        current_path = env.get("PATH", "")
        path_parts = [str(resolved_bin_dir)]
        if current_path:
            path_parts.extend(_without_repo_venv_paths(current_path.split(":")))
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
        lib_dirs.extend(_without_repo_venv_paths(current.split(":")))

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
    assets = service.assets.values if service.assets is not None else {}
    for key, flag in ASSET_FLAG_MAP.items():
        value = assets.get(key)
        if value:
            command.extend([flag, value])
            applied_keys.add(key)
    return applied_keys


def _build_vllm_command(service: ServiceSpec) -> list[str]:
    if service.model is None:
        raise ValueError(f"vllm service {service.name} is missing model")
    runtime_bin_dir = _resolve_runtime_bin_dir(service.runtime_bin_dir)
    if runtime_bin_dir is not None:
        command = [
            str(runtime_bin_dir / "vllm"),
            "serve",
            service.model,
            "--host",
            service.host,
            "--port",
            str(service.port),
        ]
    else:
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
    _apply_flag_map(command, service.args or {}, excluded_keys=asset_keys)
    _apply_loras(command, service.loras or [])
    command.extend(service.extra_args or [])
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


def _build_hindsight_plan(stack: StackSpec, service: ServiceSpec, env: dict[str, str]) -> ServiceLaunchPlan:
    if service.llm_service is None:
        raise ValueError(f"hindsight service {service.name} is missing llm_service")
    target = stack.services[service.llm_service]
    if target.model is None:
        raise ValueError(
            f"services.{service.name}.llm_service must reference a vllm service with a model"
        )
    llm_model = target.served_model_name or target.model
    llm_base_url = _service_base_url(target.host, target.port)

    runtime_bin_dir = _resolve_runtime_bin_dir(service.runtime_bin_dir)

    derived_env = dict(env)
    derived_env.update(
        {
            "HINDSIGHT_BIND_HOST": service.host,
            "HINDSIGHT_BIND_PORT": str(service.port),
            "HINDSIGHT_DATA_DIR": service.data_dir or str(Path.home() / "data" / "hindsight"),
            "HINDSIGHT_LLM_PROVIDER": "openai",
            "HINDSIGHT_LLM_MODEL": llm_model,
            "HINDSIGHT_LLM_API_KEY": derived_env.get("HINDSIGHT_LLM_API_KEY", "dummy"),
            "HINDSIGHT_LLM_BASE_URL": llm_base_url,
        }
    )
    if runtime_bin_dir is not None:
        derived_env["HINDSIGHT_RUNTIME_BIN_DIR"] = str(runtime_bin_dir)

    if _port_is_in_use(service.host, service.port):
        if _hindsight_healthcheck(service.host, service.port):
            return ServiceLaunchPlan(
                stack=stack.name,
                service=service.name,
                engine=service.engine,
                env=derived_env,
                command=["external-hindsight", f"http://{service.host}:{service.port}"],
                port=service.port,
                host=service.host,
                managed=False,
                waits_for=service.llm_service,
            )
        raise RuntimeError(
            f"services.{service.name} requested hindsight on {service.host}:{service.port}, "
            "but the port is already in use by another process"
        )

    command = ["uv", "run", "python", "scripts/hindsight_dev.py"]
    if runtime_bin_dir is not None:
        command = [str(runtime_bin_dir / "python"), "scripts/hindsight_dev.py"]

    return ServiceLaunchPlan(
        stack=stack.name,
        service=service.name,
        engine=service.engine,
        env=derived_env,
        command=command,
        port=service.port,
        host=service.host,
        managed=True,
        waits_for=service.llm_service,
    )


def build_stack_plan(
    stack_name: str,
    root: Path = STACK_ROOT,
    include_archive: bool = True,
) -> StackLaunchPlan:
    load_dotenv(dotenv_path=Path(".env"))
    stack = resolve_stack(stack_name, root=root, include_archive=include_archive)

    services: list[ServiceLaunchPlan] = []

    for service_name, service in stack.services.items():
        env = _runtime_env(service.runtime_bin_dir)
        env.update(stack.env)
        env.update(service.env)

        if service.engine == "vllm":
            services.append(
                ServiceLaunchPlan(
                    stack=stack.name,
                    service=service_name,
                    engine=service.engine,
                    env=env,
                    command=_build_vllm_command(service),
                    port=service.port,
                    host=service.host,
                )
            )
            continue

        if service.engine == "hindsight":
            services.append(_build_hindsight_plan(stack, service, env))
            continue

        raise ValueError(f"Unsupported engine in v1: {service.engine}")

    return StackLaunchPlan(stack=stack, services=services)


def _wait_for_service_exit(pid: int, timeout_seconds: float = 10.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not pid_is_running(pid):
            _reap_child_process(pid)
            return True
        time.sleep(0.1)
    if not pid_is_running(pid):
        _reap_child_process(pid)
        return True
    return False


def _reap_child_process(pid: int) -> None:
    try:
        while True:
            waited_pid, _status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == 0:
                return
            if waited_pid == pid:
                return
    except ChildProcessError:
        return


def _terminate_runtime_services(services: list[RuntimeService]) -> None:
    for service in services:
        if not service.managed or service.pid <= 0:
            continue
        try:
            pgid = os.getpgid(service.pid)
        except ProcessLookupError:
            _reap_child_process(service.pid)
            continue
        try:
            os.killpg(pgid, signal.SIGINT)
        except ProcessLookupError:
            _reap_child_process(service.pid)
            continue
        if _wait_for_service_exit(service.pid):
            continue
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            _reap_child_process(service.pid)
            continue
        if _wait_for_service_exit(service.pid):
            continue
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            _reap_child_process(service.pid)
            continue
        _wait_for_service_exit(service.pid, timeout_seconds=2.0)


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


def _wait_for_vllm_ready(service: RuntimeService, host: str) -> bool:
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


def _wait_for_dependency(plan: StackLaunchPlan, runtime_services: list[RuntimeService], dependency_name: str) -> None:
    dependency_runtime = next((service for service in runtime_services if service.name == dependency_name), None)
    if dependency_runtime is None:
        raise RuntimeError(f"Required dependency service was not launched: {dependency_name}")

    dependency_spec = plan.stack.services[dependency_name]
    if dependency_spec.engine == "vllm":
        if not _wait_for_vllm_ready(dependency_runtime, dependency_spec.host):
            raise RuntimeError(
                "Dependency service did not become ready before dependent startup. "
                f"service={dependency_name} log={dependency_runtime.log_path}"
            )
        return

    raise RuntimeError(
        f"Unsupported dependency readiness check in v1: {dependency_spec.engine}"
    )


def launch_stack(stack_name: str, root: Path = STACK_ROOT) -> RuntimeStack:
    active = read_active(prune_stale=True)
    if active is not None and any(pid_is_running(service.pid) for service in active.services):
        raise RuntimeError(f"Active stack already running: {active.stack}")

    plan = build_stack_plan(stack_name, root=root)
    runtime_services: list[RuntimeService] = []

    try:
        for service in plan.services:
            if service.waits_for is not None:
                _wait_for_dependency(plan, runtime_services, service.waits_for)

            if service.engine == "hindsight" and service.managed:
                started_runtime: RuntimeService | None = None
                latest_log_path = ""
                for attempt in range(1, HINDSIGHT_START_MAX_ATTEMPTS + 1):
                    log_path = next_log_path(plan.stack.name, service.service)
                    latest_log_path = str(log_path)
                    with log_path.open("ab") as log_handle:
                        process = subprocess.Popen(
                            service.command,
                            env=service.env,
                            stdout=log_handle,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    candidate = RuntimeService(
                        name=service.service,
                        pid=process.pid,
                        port=service.port,
                        command=service.command,
                        log_path=str(log_path),
                        started_at=time.time(),
                        managed=True,
                    )
                    if _wait_for_hindsight_ready(candidate, service.host):
                        started_runtime = candidate
                        runtime_services.append(started_runtime)
                        break
                    _terminate_runtime_services([candidate])
                    if attempt < HINDSIGHT_START_MAX_ATTEMPTS:
                        print(
                            f"warning: hindsight startup attempt {attempt}/{HINDSIGHT_START_MAX_ATTEMPTS} failed; retrying...",
                            flush=True,
                        )
                        time.sleep(HINDSIGHT_START_RETRY_DELAY_SECONDS)
                if started_runtime is None:
                    raise RuntimeError(
                        "Hindsight service failed to become ready after retries. "
                        f"See latest log: {latest_log_path}"
                    )
                continue

            if service.engine == "hindsight" and not service.managed:
                print(
                    f"Hindsight already up and running at http://{service.host}:{service.port}; reusing"
                )
                runtime_services.append(
                    RuntimeService(
                        name=service.service,
                        pid=0,
                        port=service.port,
                        command=service.command,
                        log_path="(external)",
                        started_at=time.time(),
                        managed=False,
                    )
                )
                continue

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
    except Exception:
        _terminate_runtime_services(runtime_services)
        raise
