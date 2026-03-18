from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(".agentmux")
STATE_DIR = RUNTIME_ROOT / "state"
LOG_DIR = RUNTIME_ROOT / "logs"
ACTIVE_PATH = STATE_DIR / "active.json"
HISTORY_PATH = STATE_DIR / "history.jsonl"


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
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_active(runtime_stack: RuntimeStack) -> None:
    ensure_runtime_dirs()
    ACTIVE_PATH.write_text(json.dumps(asdict(runtime_stack), indent=2) + "\n", encoding="utf-8")
    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(runtime_stack)) + "\n")


def read_active() -> RuntimeStack | None:
    if not ACTIVE_PATH.exists():
        return None
    data = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    services = [RuntimeService(**service) for service in data["services"]]
    return RuntimeStack(
        stack=data["stack"],
        track=data["track"],
        path=data["path"],
        services=services,
        started_at=data["started_at"],
    )


def clear_active() -> None:
    if ACTIVE_PATH.exists():
        ACTIVE_PATH.unlink()


def load_history(limit: int = 20) -> list[RuntimeStack]:
    if not HISTORY_PATH.exists():
        return []
    entries: list[RuntimeStack] = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()[-limit:]:
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
    return LOG_DIR / f"{stamp}-{stack_name}-{service_name}.log"
