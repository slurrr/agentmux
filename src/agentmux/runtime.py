from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

def _runtime_root() -> Path:
    configured = os.environ.get("AGENTMUX_RUN_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "runs" / "agentmux"


def runtime_root() -> Path:
    return _runtime_root()


def state_dir() -> Path:
    return runtime_root() / "state"


def log_dir() -> Path:
    return runtime_root() / "logs"


def active_path() -> Path:
    return state_dir() / "active.json"


def history_path() -> Path:
    return state_dir() / "history.jsonl"


@dataclass(frozen=True)
class RuntimeService:
    name: str
    pid: int
    port: int
    command: list[str]
    log_path: str
    started_at: float


@dataclass(frozen=True)
class RuntimeStack:
    stack: str
    track: str
    path: str
    services: list[RuntimeService]
    started_at: float


def ensure_runtime_dirs() -> None:
    state_dir().mkdir(parents=True, exist_ok=True)
    log_dir().mkdir(parents=True, exist_ok=True)


def write_active(runtime_stack: RuntimeStack) -> None:
    ensure_runtime_dirs()
    active_path().write_text(json.dumps(asdict(runtime_stack), indent=2) + "\n", encoding="utf-8")
    with history_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(runtime_stack)) + "\n")


def read_active(*, prune_stale: bool = False) -> RuntimeStack | None:
    path = active_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    services = [RuntimeService(**service) for service in data["services"]]
    runtime_stack = RuntimeStack(
        stack=data["stack"],
        track=data["track"],
        path=data["path"],
        services=services,
        started_at=data["started_at"],
    )
    if prune_stale and runtime_stack.services and not any(pid_is_running(service.pid) for service in runtime_stack.services):
        clear_active()
        return None
    return runtime_stack


def clear_active() -> None:
    path = active_path()
    if path.exists():
        path.unlink()


def load_history(limit: int = 20) -> list[RuntimeStack]:
    path = history_path()
    if not path.exists():
        return []
    entries: list[RuntimeStack] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        if not line.strip():
            continue
        data = json.loads(line)
        services = [RuntimeService(**service) for service in data["services"]]
        entries.append(
            RuntimeStack(
                stack=data["stack"],
                track=data["track"],
                path=data["path"],
                services=services,
                started_at=data["started_at"],
            )
        )
    return entries


def pid_is_running(pid: int) -> bool:
    proc_dir = Path("/proc") / str(pid)
    stat_path = proc_dir / "stat"
    if stat_path.exists():
        try:
            stat_fields = stat_path.read_text(encoding="utf-8").split()
        except OSError:
            stat_fields = []
        if len(stat_fields) >= 3 and stat_fields[2] == "Z":
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def runtime_status(runtime_stack: RuntimeStack | None) -> dict[str, Any]:
    if runtime_stack is None:
        return {"active": False, "stack": None, "services": []}

    services = []
    for service in runtime_stack.services:
        services.append(
            {
                "name": service.name,
                "pid": service.pid,
                "port": service.port,
                "running": pid_is_running(service.pid),
                "log_path": service.log_path,
                "started_at": service.started_at,
            }
        )

    return {
        "active": any(item["running"] for item in services),
        "stack": runtime_stack.stack,
        "track": runtime_stack.track,
        "path": runtime_stack.path,
        "started_at": runtime_stack.started_at,
        "services": services,
    }


def stop_runtime(runtime_stack: RuntimeStack) -> None:
    for service in runtime_stack.services:
        try:
            os.killpg(os.getpgid(service.pid), signal.SIGTERM)
        except ProcessLookupError:
            continue
    clear_active()


def next_log_path(stack_name: str, service_name: str) -> Path:
    ensure_runtime_dirs()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return log_dir() / f"{stamp}-{stack_name}-{service_name}.log"
