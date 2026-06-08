from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path

from agentmux import __version__
from agentmux.bench import BenchmarkError, run_benchmark
from agentmux.bench_report import read_result, render_detailed_report
from agentmux.bench_session import DEFAULT_REPO, BenchSessionError, run_bench_session
from agentmux.config import STACK_ROOT, list_stacks, resolve_stack
from agentmux.onboard import OnboardingError, onboard_model, render_onboard_summary
from agentmux.runner import build_stack_plan, launch_stack
from agentmux.runtime import (
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

    bench_parser = subparsers.add_parser("bench", help="Benchmark a stack")
    bench_parser.add_argument("stack", help="Stack name")
    bench_parser.add_argument(
        "--launch",
        action="store_true",
        help="Launch the stack for this benchmark run, then benchmark it",
    )
    bench_parser.add_argument(
        "--keep-running",
        action="store_true",
        help="With --launch, leave the launched stack running after the benchmark",
    )
    bench_parser.add_argument(
        "--judge",
        action="store_true",
        help="Run end-of-run judge audit and store audit JSON in result",
    )
    bench_parser.add_argument(
        "--no-perf",
        action="store_true",
        help="Skip endpoint perf for this run",
    )

    bench_show_parser = subparsers.add_parser(
        "bench-show",
        help="Show a benchmark result in a human-readable format",
        description=(
            "Show a saved benchmark result as a readable terminal report. "
            "If RESULT is omitted, the latest benchmark JSON is used."
        ),
        epilog=(
            "examples:\n"
            "  agentmux bench-show\n"
            "  agentmux bench-show qwen3_5-bench\n"
            "  agentmux bench-show /path/to/result.json\n"
            "  agentmux bench-show --failures-only\n"
            "  agentmux bench-show --judge-flagged-only\n"
            "  agentmux bench-show --case bounded_structured_summary\n"
            "  agentmux bench-show --full\n"
            "  agentmux bench-show picked --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bench_show_parser.add_argument(
        "result",
        nargs="?",
        help="Benchmark result path or filename fragment; defaults to latest result",
    )
    bench_show_parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw benchmark JSON instead of the formatted report",
    )
    bench_show_parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Show only failed cases",
    )
    bench_show_parser.add_argument(
        "--judge-flagged-only",
        action="store_true",
        help="Show only judge-flagged cases",
    )
    bench_show_parser.add_argument(
        "--case",
        help="Show only cases whose id contains this string",
    )
    bench_show_parser.add_argument(
        "--full",
        action="store_true",
        help="Show full prompt/response text without truncation",
    )

    bench_session_parser = subparsers.add_parser(
        "bench-session",
        help="Launch a manual sandboxed pi session for benchmark-style evaluation",
    )
    bench_session_parser.add_argument("stack", help="Stack name")
    bench_session_parser.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO,
        help=f"Source git repo path (default: {DEFAULT_REPO})",
    )
    bench_session_parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable network in the sandbox",
    )
    bench_session_parser.add_argument(
        "--preserve",
        action="store_true",
        help="Preserve session worktree instead of tearing down on success",
    )

    onboard_parser = subparsers.add_parser("onboard", help="Onboard a new model from HF cache")
    onboard_parser.add_argument("source", type=Path, help="HF cache path or snapshot directory")
    onboard_parser.add_argument("--name", help="Optional stack/model slug")
    onboard_parser.add_argument(
        "--track",
        default="lab",
        choices=["core", "lab", "bench", "archive"],
        help="Mux track for the generated manifest",
    )
    onboard_parser.add_argument(
        "--instructions",
        help="Freeform onboarding instructions to record in the manifest",
    )
    onboard_parser.add_argument(
        "--service",
        action="append",
        choices=["memory"],
        default=[],
        help="Add an extra service to the generated mux (repeatable)",
    )
    onboard_parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Do not try to launch the generated stack",
    )
    onboard_parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip the smoke evaluation step",
    )
    onboard_parser.add_argument(
        "--bench",
        action="store_true",
        help="Run the benchmark profile after onboarding",
    )
    onboard_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pointers/manifests if needed",
    )
    onboard_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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


def _format_render_command(command: list[str]) -> str:
    if not command:
        return ""
    head_end = 1
    while head_end < len(command) and not command[head_end].startswith("-"):
        head_end += 1
    lines = [f"  {shlex.join(command[:head_end])}"]
    index = head_end
    while index < len(command):
        token = command[index]
        if token.startswith("-") and index + 1 < len(command) and not command[index + 1].startswith("-"):
            lines.append(f"    {token} {shlex.quote(command[index + 1])}")
            index += 2
        else:
            lines.append(f"    {shlex.quote(token)}")
            index += 1
    return "\n".join(lines)


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
        for index, service in enumerate(plan.services):
            if index:
                print()
            prefix = " (reuse)" if not service.managed else ""
            print(f"[{service.service}]{prefix}")
            print(_format_render_command(service.command))
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


def _wait_for_bench_ready(base_url: str, timeout_seconds: float = 180.0) -> float:
    started_at = time.time()
    deadline = started_at + timeout_seconds
    while time.time() < deadline:
        try:
            _ensure_bench_reachable(base_url)
            return time.time() - started_at
        except Exception:
            time.sleep(0.5)
    _ensure_bench_reachable(base_url)
    return time.time() - started_at


def _ensure_bench_reachable(base_url: str) -> None:
    import requests

    response = requests.get(f"{base_url}/models", timeout=10)
    response.raise_for_status()


def _run_benchmark_with_launch(
    stack_name: str,
    root: Path,
    keep_running: bool,
    judge: bool = False,
    no_perf: bool = False,
) -> tuple[dict[str, object], Path, str]:
    stack = resolve_stack(stack_name, root=root)
    service = stack.services[stack.primary_service]
    launch_started_at = time.time()
    service_args = getattr(service, "args", None)
    previous_max_num_seqs = (service_args or {}).get("max_num_seqs") if service_args else None
    bench_vllm_overrides = {"max_num_seqs": 32}
    runtime_stack = launch_stack(
        stack_name,
        root=root,
        vllm_arg_overrides=bench_vllm_overrides,
    )
    primary_runtime = next(
        runtime_service
        for runtime_service in runtime_stack.services
        if runtime_service.name == stack.primary_service
    )
    base_url = _service_base_url(service.host, service.port)
    try:
        startup_ok = _follow_startup_log(Path(primary_runtime.log_path), primary_runtime.pid)
        if not startup_ok:
            raise BenchmarkError(
                "launched stack exited before startup completed; "
                f"see log: {primary_runtime.log_path}"
            )
        ready_seconds = _wait_for_bench_ready(base_url)
        launch_observation = {
            "source": "agentmux_launch",
            "launch_started_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(launch_started_at)
            ),
            "ready_after_seconds": round(ready_seconds, 3),
            "kept_running": keep_running,
            "bench_overrides": {
                "vllm_args": {
                    "max_num_seqs": {
                        "before": previous_max_num_seqs,
                        "after": 32,
                        "reason": "bench endpoint perf standardizes concurrency up to 16",
                    }
                }
            },
        }
        return run_benchmark(
            stack_name,
            root,
            target_mode="launched",
            launch_observation=launch_observation,
            judge_audit=judge,
            enable_perf=not no_perf,
        )
    finally:
        if not keep_running:
            stop_runtime(runtime_stack)


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

    if args.command == "bench":
        try:
            if args.launch:
                _result, _path, summary = _run_benchmark_with_launch(
                    args.stack,
                    args.root,
                    args.keep_running,
                    args.judge,
                    args.no_perf,
                )
            else:
                _result, _path, summary = run_benchmark(
                    args.stack,
                    args.root,
                    judge_audit=args.judge,
                    enable_perf=not args.no_perf,
                )
        except BenchmarkError as exc:
            raise SystemExit(str(exc)) from exc
        except Exception as exc:
            raise SystemExit(f"benchmark failed: {exc}") from exc
        print(summary)
        return 0

    if args.command == "bench-show":
        try:
            result, path = read_result(args.result)
        except FileNotFoundError as exc:
            raise SystemExit(str(exc)) from exc
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                render_detailed_report(
                    result,
                    path,
                    failures_only=args.failures_only,
                    judge_flagged_only=args.judge_flagged_only,
                    case_filter=args.case,
                    full=args.full,
                )
            )
        return 0

    if args.command == "bench-session":
        try:
            _summary, message = run_bench_session(
                args.stack,
                args.root,
                repo=args.repo,
                offline=args.offline,
                preserve=args.preserve,
            )
        except BenchSessionError as exc:
            raise SystemExit(str(exc)) from exc
        except Exception as exc:
            raise SystemExit(f"bench-session failed: {exc}") from exc
        print(message)
        return 0

    if args.command == "onboard":
        try:
            result = onboard_model(
                args.source,
                stack_name=args.name,
                track=args.track,
                instructions=args.instructions,
                services=list(args.service),
                launch=not args.no_launch,
                smoke=not args.no_smoke,
                bench=args.bench,
                force=args.force,
            )
        except OnboardingError as exc:
            raise SystemExit(str(exc)) from exc
        if args.json:
            print(json.dumps(result.__dict__, indent=2))
        else:
            print(render_onboard_summary(result), end="")
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
