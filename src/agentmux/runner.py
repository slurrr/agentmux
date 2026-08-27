from __future__ import annotations

import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from agentmux.config import MUX_ROOT, MuxSpec, ServiceSpec, resolve_mux
from agentmux.runtime import (
    RuntimeService,
    RuntimeStack,
    clear_active,
    container_is_running,
    read_active,
    write_active,
)

DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0
STARTUP_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class ServiceLaunchPlan:
    mux: str
    service: str
    image: str
    container_name: str
    host: str
    port: int
    health_path: str
    command: list[str]

    def shell_command(self) -> str:
        return shlex.join(self.command)

    @property
    def health_url(self) -> str:
        path = self.health_path if self.health_path.startswith("/") else f"/{self.health_path}"
        return f"http://{self.host}:{self.port}{path}"


@dataclass(frozen=True)
class MuxLaunchPlan:
    mux: MuxSpec
    services: list[ServiceLaunchPlan]


def _build_podman_run(service: ServiceSpec, *, image: str | None = None) -> list[str]:
    command = ["podman", "run", "--detach", "--replace", "--name", service.container_name]
    if service.runtime_dir:
        log_path = Path(service.runtime_dir) / "podman.log"
        command.extend(["--log-driver", "k8s-file", "--log-opt", f"path={log_path}"])
    command.extend(service.podman_args)

    for key in sorted(service.env):
        command.extend(["--env", f"{key}={service.env[key]}"])

    for key in sorted(service.labels):
        command.extend(["--label", f"{key}={service.labels[key]}"])

    for port in service.ports:
        command.extend(["--publish", port])

    for volume in service.volumes:
        command.extend(["--volume", volume.podman_value()])

    command.append(image or service.image)
    command.extend(service.command)
    return command


def build_mux_plan(
    mux_name: str,
    root: Path = MUX_ROOT,
    *,
    image_override: str | None = None,
) -> MuxLaunchPlan:
    mux = resolve_mux(mux_name, root=root)
    services = [
        ServiceLaunchPlan(
            mux=mux.name,
            service=service.name,
            image=image_override or service.image,
            container_name=service.container_name,
            host=service.host,
            port=service.port,
            health_path=service.health_path,
            command=_build_podman_run(service, image=image_override),
        )
        for service in mux.services.values()
    ]
    return MuxLaunchPlan(mux=mux, services=services)


def _health_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def _wait_for_ready(service: ServiceLaunchPlan, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _health_ready(service.health_url):
            return True
        if not container_is_running(service.container_name):
            return False
        time.sleep(STARTUP_POLL_SECONDS)
    return _health_ready(service.health_url)


def launch_mux(
    mux_name: str,
    root: Path = MUX_ROOT,
    *,
    image_override: str | None = None,
    wait: bool = True,
    timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
) -> RuntimeStack:
    active = read_active(prune_stale=True)
    active_running = active is not None and any(
        container_is_running(service.container_name) for service in active.services
    )
    if active_running:
        assert active is not None
        raise RuntimeError(f"Active mux already running: {active.mux}")

    plan = build_mux_plan(mux_name, root=root, image_override=image_override)
    runtime_services: list[RuntimeService] = []

    try:
        for service in plan.services:
            service_spec = plan.mux.services[service.service]
            if service_spec.runtime_dir is not None:
                Path(service_spec.runtime_dir).mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                service.command,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            container_id = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            runtime_service = RuntimeService(
                name=service.service,
                container_name=service.container_name,
                container_id=container_id,
                image=service.image,
                host=service.host,
                port=service.port,
                command=service.command,
                health_url=service.health_url,
                started_at=time.time(),
                managed=True,
            )
            runtime_services.append(runtime_service)
            if wait and not _wait_for_ready(service, timeout_seconds):
                raise RuntimeError(
                    f"Service did not become ready: {service.service} ({service.health_url})"
                )

        runtime_stack = RuntimeStack(
            mux=plan.mux.name,
            track=plan.mux.track,
            path=str(plan.mux.path),
            services=runtime_services,
            started_at=time.time(),
        )
        write_active(runtime_stack)
        return runtime_stack
    except Exception:
        for service in reversed(runtime_services):
            subprocess.run(["podman", "rm", "--force", service.container_name], check=False)
        clear_active()
        raise
