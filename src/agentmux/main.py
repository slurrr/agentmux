from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from agentmux import __version__
from agentmux.config import STACK_ROOT, list_stacks, resolve_stack
from agentmux.runner import build_stack_plan, launch_stack
from agentmux.runtime import (
    clear_active,
    load_history,
    pid_is_running,
    read_active,
    runtime_status,
    stop_runtime,
)
from agentmux.smoke import smoke_stack_safe

STARTUP_READY_MARKER = "Application startup complete."
STARTUP_EXIT_SETTLE_SECONDS = 1.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentmux", description="Stack-first backend cockpit")
    parser.add_argument("--root", type=Path, default=STACK_ROOT, help="Stack manifest root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available stacks")
    list_parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Include archived stacks",
    )

    show_parser = subparsers.add_parser("show", help="Show a stack manifest")
    show_parser.add_argument("stack", help="Stack name")
    show_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    render_parser = subparsers.add_parser("render", help="Render launch commands for a stack")
    render_parser.add_argument("stack", help="Stack name")
    render_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    up_parser = subparsers.add_parser("up", help="Launch a stack")
    up_parser.add_argument("stack", help="Stack name")
    up_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without launching",
    )

    down_parser = subparsers.add_parser("down", help="Stop the active stack")
    down_parser.add_argument("stack", nargs="?", help="Optional stack name guard")

    status_parser = subparsers.add_parser("status", help="Show active runtime state")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    smoke_parser = subparsers.add_parser("smoke", help="Run OpenAI-compatible smoke tests")
    smoke_parser.add_argument("stack", nargs="?", help="Stack name, defaults to active stack")
    smoke_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    history_parser = subparsers.add_parser("history", help="Show recent stack launch history")
    history_parser.add_argument("--limit", type=int, default=10, help="Number of history entries")

    subparsers.add_parser("version", help="Print the CLI version")
    return parser


def _stack_payload(stack_name: str, root: Path, include_archive: bool = True) -> dict[str, object]:
    stack = resolve_stack(stack_name, root=root, include_archive=include_archive)
    return {
        "name": stack.name,
        "track": stack.track,
        "path": str(stack.path),
        "primary_service": stack.primary_service,
        "notes": stack.notes,
        "services": {
            name: {
                "engine": service.engine,
                "model": service.model,
                "host": service.host,
                "port": service.port,
                "served_model_name": service.served_model_name,
                "env": service.env,
                "args": service.args,
                "extra_args": service.extra_args,
                "assets": (service.assets.values if service.assets is not None else {}),
                "loras": [
                    {
                        "name": lora.name,
                        "path": lora.path,
                        "base_model": lora.base_model,
                        "enabled": lora.enabled,
                    }
                    for lora in (service.loras or [])
                ],
                "data_dir": service.data_dir,
                "llm_service": service.llm_service,
                "notes": service.notes,
            }
            for name, service in stack.services.items()
        },
    }


def _print_show(stack_name: str, root: Path, as_json: bool) -> int:
    stack = resolve_stack(stack_name, root=root)
    payload = _stack_payload(stack_name, root)
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"name: {stack.name}")
    print(f"track: {stack.track}")
    print(f"primary_service: {stack.primary_service}")
    print(f"path: {stack.path}")
    print(f"notes: {stack.notes or '-'}")
    print("services:")
    for service_name, service in stack.services.items():
        print(f"  {service_name}: {service.engine} {service.model} @ {service.host}:{service.port}")
    return 0


def _print_render(stack_name: str, root: Path, as_json: bool) -> int:
    plan = build_stack_plan(stack_name, root=root)
    payload = {
        "stack": plan.stack.name,
        "track": plan.stack.track,
        "services": [
            {
                "name": service.service,
                "engine": service.engine,
                "port": service.port,
                "host": service.host,
                "managed": service.managed,
                "waits_for": service.waits_for,
                "command": service.command,
                "env": {
                    key: service.env[key]
                    for key in sorted(plan.stack.env | plan.stack.services[service.service].env)
                },
            }
            for service in plan.services
        ],
    }
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for service in plan.services:
            prefix = "(reuse) " if not service.managed else ""
            print(f"[{service.service}] {prefix}{service.shell_command()}")
    return 0


def _print_status(as_json: bool) -> int:
    payload = runtime_status(read_active(prune_stale=True))
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    if not payload["stack"]:
        print("no active stack")
        return 0
    print(f"stack: {payload['stack']}")
    print(f"track: {payload['track']}")
    for service in payload["services"]:
        state = "running" if service["running"] else "stopped"
        print(f"  {service['name']}: {state} pid={service['pid']} port={service['port']}")
        print(f"    log: {service['log_path']}")
    return 0


def _display_host(host: str) -> str:
    return "127.0.0.1" if host == "0.0.0.0" else host


def _service_base_url(host: str, port: int) -> str:
    return f"http://{_display_host(host)}:{port}/v1"


def _follow_startup_log(log_path: Path, pid: int) -> bool:
    offset = 0
    exit_seen_at: float | None = None
    while True:
        if log_path.exists():
            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
            if chunk:
                print(chunk, end="", flush=True)
                if STARTUP_READY_MARKER in chunk:
                    return True
        if not pid_is_running(pid) and log_path.exists():
            if exit_seen_at is None:
                exit_seen_at = time.time()
            elif time.time() - exit_seen_at >= STARTUP_EXIT_SETTLE_SECONDS:
                if log_path.exists():
                    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        chunk = handle.read()
                    if chunk:
                        print(chunk, end="", flush=True)
                return False
        time.sleep(0.1)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        for stack in list_stacks(args.root, include_archive=args.include_archive):
            print(f"{stack.track}/{stack.name}")
        return 0

    if args.command == "show":
        return _print_show(args.stack, args.root, args.json)

    if args.command == "render":
        return _print_render(args.stack, args.root, args.json)

    if args.command == "up":
        if args.dry_run:
            return _print_render(args.stack, args.root, False)
        stack = resolve_stack(args.stack, root=args.root)
        runtime_stack = launch_stack(args.stack, root=args.root)
        print(f"started stack: {runtime_stack.stack}")
        for service in runtime_stack.services:
            if service.name in stack.services:
                service_spec = stack.services[service.name]
                url = _service_base_url(service_spec.host, service.port)
            else:
                url = f"http://127.0.0.1:{service.port}"
            managed_note = "" if service.managed else " (external)"
            print(
                f"  {service.name}: pid={service.pid} port={service.port} "
                f"url={url} log={service.log_path}{managed_note}"
            )
        return 0

    if args.command == "down":
        active = read_active(prune_stale=True)
        if active is None:
            print("no active stack")
            return 0
        if args.stack and args.stack != active.stack:
            raise SystemExit(f"Active stack is {active.stack}, not {args.stack}")
        stop_runtime(active)
        clear_active()
        print(f"stopped stack: {active.stack}")
        return 0

    if args.command == "status":
        return _print_status(args.json)

    if args.command == "smoke":
        stack_name = args.stack
        if stack_name is None:
            active = read_active(prune_stale=True)
            if active is None:
                raise SystemExit("No active stack and no stack name provided")
            stack_name = active.stack
        result = smoke_stack_safe(resolve_stack(stack_name, root=args.root))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.command == "history":
        for item in load_history(limit=args.limit):
            print(f"{item.stack} ({item.track}) started_at={item.started_at:.0f}")
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
