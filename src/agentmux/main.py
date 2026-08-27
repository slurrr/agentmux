from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agentmux import __version__
from agentmux.config import MUX_ROOT, iter_muxes, resolve_mux
from agentmux.runner import build_mux_plan, launch_mux
from agentmux.runtime import (
    format_age,
    load_history,
    read_active,
    runtime_status,
    stop_runtime,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentmux", description="Container-first mux cockpit")
    parser.add_argument("--root", type=Path, default=MUX_ROOT, help="Mux manifest root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List muxes")

    show_parser = subparsers.add_parser("show", help="Show mux configuration")
    show_parser.add_argument("mux")
    show_parser.add_argument("--json", action="store_true")

    render_parser = subparsers.add_parser("render", help="Render Podman launch commands")
    render_parser.add_argument("mux")
    render_parser.add_argument("--json", action="store_true")
    render_parser.add_argument(
        "--image",
        help="Temporarily substitute the service image without editing mux.toml",
    )

    up_parser = subparsers.add_parser("up", help="Launch a mux")
    up_parser.add_argument("mux")
    up_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render commands without launching",
    )
    up_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for health endpoints",
    )
    up_parser.add_argument(
        "--timeout", type=float, default=300.0, help="Readiness timeout seconds (default: 300)"
    )
    up_parser.add_argument(
        "--image",
        help="Temporarily substitute the service image without editing mux.toml",
    )

    down_parser = subparsers.add_parser("down", help="Remove active mux containers")
    down_parser.add_argument("mux", nargs="?", help="Optional mux name guard")

    status_parser = subparsers.add_parser("status", help="Show active runtime state")
    status_parser.add_argument("--json", action="store_true")

    logs_parser = subparsers.add_parser("logs", help="Show logs for an active service")
    logs_parser.add_argument(
        "service",
        nargs="?",
        help="Service name, defaults to primary/first active",
    )
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow logs")

    history_parser = subparsers.add_parser("history", help="Show recent launches")
    history_parser.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("version", help="Print version")
    return parser


def _service_payload(service: Any) -> dict[str, Any]:
    return asdict(service)  # dataclass service specs stay intentionally flat


def _mux_payload(name: str, root: Path) -> dict[str, Any]:
    mux = resolve_mux(name, root=root)
    return {
        "name": mux.name,
        "track": mux.track,
        "path": str(mux.path),
        "primary_service": mux.primary_service,
        "notes": mux.notes,
        "services": {name: _service_payload(service) for name, service in mux.services.items()},
    }


def _format_command(command: list[str]) -> str:
    if not command:
        return ""
    lines = [f"  {shlex.join(command[:6])}"]
    index = 6
    while index < len(command):
        token = command[index]
        if (
            token in {"--env", "--label", "--publish", "--volume", "--name"}
            and index + 1 < len(command)
        ):
            lines.append(f"    {token} {shlex.quote(command[index + 1])}")
            index += 2
        elif (
            token.startswith("-")
            and index + 1 < len(command)
            and not command[index + 1].startswith("-")
        ):
            lines.append(f"    {token} {shlex.quote(command[index + 1])}")
            index += 2
        else:
            lines.append(f"    {shlex.quote(token)}")
            index += 1
    return " \\\n".join(lines)


def _print_list(root: Path) -> int:
    muxes = iter_muxes(root)
    if not muxes:
        print("no muxes found")
        return 0
    for mux in muxes:
        print(f"{mux.name}\t{mux.track}\t{mux.path}")
    return 0


def _print_show(name: str, root: Path, as_json: bool) -> int:
    payload = _mux_payload(name, root)
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"name: {payload['name']}")
    print(f"track: {payload['track']}")
    print(f"primary_service: {payload['primary_service']}")
    print(f"path: {payload['path']}")
    print(f"notes: {payload['notes'] or '-'}")
    print("services:")
    for service_name, service in payload["services"].items():
        assert isinstance(service, dict)
        print(
            f"  {service_name}: {service['image']} "
            f"container={service['container_name']} port={service['port']}"
        )
    return 0


def _render_payload(
    name: str,
    root: Path,
    *,
    image_override: str | None = None,
) -> dict[str, Any]:
    plan = build_mux_plan(name, root=root, image_override=image_override)
    return {
        "mux": plan.mux.name,
        "track": plan.mux.track,
        "path": str(plan.mux.path),
        "services": [
            {
                "name": service.service,
                "image": service.image,
                "container_name": service.container_name,
                "host": service.host,
                "port": service.port,
                "health_url": service.health_url,
                "command": service.command,
            }
            for service in plan.services
        ],
    }


def _print_render(
    name: str,
    root: Path,
    as_json: bool,
    image_override: str | None = None,
) -> int:
    payload = _render_payload(name, root, image_override=image_override)
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    for index, service in enumerate(payload["services"]):
        assert isinstance(service, dict)
        if index:
            print()
        print(f"[{service['name']}] {service['container_name']}")
        command = service["command"]
        assert isinstance(command, list)
        print(_format_command([str(part) for part in command]))
    return 0


def _print_status(as_json: bool) -> int:
    payload = runtime_status(read_active(prune_stale=True))
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    if not payload["mux"]:
        print("no active mux")
        return 0
    print(f"mux: {payload['mux']}")
    print(f"track: {payload['track']}")
    for service in payload["services"]:
        state = "running" if service["running"] else service["status"]
        print(
            f"  {service['name']}: {state} container={service['container_name']} "
            f"port={service['port']} age={format_age(float(service['started_at']))}"
        )
        print(f"    image: {service['image']}")
        print(f"    health: {service['health_url']}")
    return 0


def _run_up(args: argparse.Namespace) -> int:
    if args.dry_run:
        return _print_render(args.mux, args.root, as_json=False, image_override=args.image)
    runtime = launch_mux(
        args.mux,
        root=args.root,
        image_override=args.image,
        wait=not args.no_wait,
        timeout_seconds=args.timeout,
    )
    print(f"launched mux: {runtime.mux}")
    for service in runtime.services:
        print(f"  {service.name}: {service.container_name} {service.health_url}")
    return 0


def _run_down(name_guard: str | None) -> int:
    active = read_active(prune_stale=False)
    if active is None:
        print("no active mux")
        return 0
    if name_guard is not None and active.mux != name_guard:
        raise RuntimeError(f"active mux is {active.mux}, not {name_guard}")
    stop_runtime(active)
    print(f"removed mux containers: {active.mux}")
    return 0


def _run_logs(service_name: str | None, follow: bool) -> int:
    active = read_active(prune_stale=True)
    if active is None:
        raise RuntimeError("no active mux")
    if service_name is None:
        service = active.services[0]
    else:
        matches = [service for service in active.services if service.name == service_name]
        if not matches:
            raise RuntimeError(f"active mux has no service named {service_name}")
        service = matches[0]
    command = ["podman", "logs"]
    if follow:
        command.append("--follow")
    command.append(service.container_name)
    return subprocess.run(command, check=False).returncode


def _print_history(limit: int) -> int:
    entries = load_history(limit=limit)
    if not entries:
        print("no history")
        return 0
    for entry in entries:
        containers = ", ".join(service.container_name for service in entry.services)
        print(f"{entry.mux}\t{entry.track}\t{format_age(entry.started_at)} ago\t{containers}")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            return _print_list(args.root)
        if args.command == "show":
            return _print_show(args.mux, args.root, args.json)
        if args.command == "render":
            return _print_render(args.mux, args.root, args.json, image_override=args.image)
        if args.command == "up":
            return _run_up(args)
        if args.command == "down":
            return _run_down(args.mux)
        if args.command == "status":
            return _print_status(args.json)
        if args.command == "logs":
            return _run_logs(args.service, args.follow)
        if args.command == "history":
            return _print_history(args.limit)
        if args.command == "version":
            print(__version__)
            return 0
    except Exception as exc:
        print(f"agentmux: error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
