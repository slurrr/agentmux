from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def runtime_root() -> Path:
    configured = os.environ.get("AGENTMUX_RUN_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "runs" / "agentmux"


def state_dir() -> Path:
    return runtime_root() / "state"


def active_path() -> Path:
    return state_dir() / "active.json"


def history_path() -> Path:
    return state_dir() / "history.jsonl"


@dataclass(frozen=True)
class RuntimeService:
    name: str
    container_name: str
    container_id: str
    image: str
    host: str
    port: int
    command: list[str]
    health_url: str
    started_at: float
    managed: bool = True


@dataclass(frozen=True)
class RuntimeStack:
    mux: str
    track: str
    path: str
    services: list[RuntimeService]
    started_at: float


def ensure_runtime_dirs() -> None:
    state_dir().mkdir(parents=True, exist_ok=True)


def write_active(runtime_stack: RuntimeStack) -> None:
    ensure_runtime_dirs()
    payload = json.dumps(asdict(runtime_stack), indent=2) + "\n"
    active_path().write_text(payload, encoding="utf-8")
    with history_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(runtime_stack)) + "\n")


def _runtime_stack_from_data(data: dict[str, Any]) -> RuntimeStack:
    return RuntimeStack(
        mux=data["mux"],
        track=data["track"],
        path=data["path"],
        services=[RuntimeService(**service) for service in data["services"]],
        started_at=data["started_at"],
    )


def read_active(*, prune_stale: bool = False) -> RuntimeStack | None:
    path = active_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "mux" not in data:
        if prune_stale:
            clear_active()
            return None
        legacy_name = data.get("stack", "legacy")
        raise RuntimeError(
            f"active runtime state is from legacy AgentMux stack '{legacy_name}'; "
            f"remove {path} or run status with pruning"
        )
    runtime_stack = _runtime_stack_from_data(data)
    if prune_stale and runtime_stack.services and not any(
        container_is_running(service.container_name) for service in runtime_stack.services
    ):
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
        if line.strip():
            entries.append(_runtime_stack_from_data(json.loads(line)))
    return entries


def _podman(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["podman", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def container_is_running(container_name: str) -> bool:
    result = _podman(["inspect", "--format", "{{.State.Running}}", container_name])
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def container_status(container_name: str) -> str:
    result = _podman(["inspect", "--format", "{{.State.Status}}", container_name])
    if result.returncode != 0:
        return "missing"
    return result.stdout.strip() or "unknown"


def runtime_status(runtime_stack: RuntimeStack | None) -> dict[str, Any]:
    if runtime_stack is None:
        return {"active": False, "mux": None, "services": []}

    services: list[dict[str, Any]] = []
    for service in runtime_stack.services:
        running = container_is_running(service.container_name)
        services.append(
            {
                "name": service.name,
                "container_name": service.container_name,
                "container_id": service.container_id,
                "image": service.image,
                "host": service.host,
                "port": service.port,
                "health_url": service.health_url,
                "running": running,
                "status": "running" if running else container_status(service.container_name),
                "started_at": service.started_at,
            }
        )

    return {
        "active": any(item["running"] for item in services),
        "mux": runtime_stack.mux,
        "track": runtime_stack.track,
        "path": runtime_stack.path,
        "started_at": runtime_stack.started_at,
        "services": services,
    }


def stop_runtime(runtime_stack: RuntimeStack) -> None:
    for service in reversed(runtime_stack.services):
        if service.managed:
            subprocess.run(["podman", "rm", "--force", service.container_name], check=False)
    clear_active()


def format_age(started_at: float) -> str:
    seconds = max(0, int(time.time() - started_at))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"
