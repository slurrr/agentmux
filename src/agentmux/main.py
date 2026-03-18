from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentmux import __version__
from agentmux.config import DEFAULT_CONFIG_PATH, load_profile, profile_names
from agentmux.runner import build_launch_plan, run_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentmux",
        description="Profile-driven vLLM launcher",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to agentmux TOML",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List configured launch profiles")

    show_parser = subparsers.add_parser("show", help="Show a launch profile")
    show_parser.add_argument("profile", help="Profile name to inspect")

    render_parser = subparsers.add_parser("render", help="Render the uv/vllm command for a profile")
    render_parser.add_argument("profile", help="Profile name to render")
    render_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    serve_parser = subparsers.add_parser("serve", help="Launch vLLM using a named profile")
    serve_parser.add_argument("profile", help="Profile name to launch")
    serve_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command without running it",
    )

    subparsers.add_parser("version", help="Print the CLI version")

    return parser


def _print_profile(config_path: Path, profile_name: str) -> int:
    profile = load_profile(profile_name, config_path)
    print(f"name: {profile.name}")
    print(f"model: {profile.model}")
    print(f"served_model_name: {profile.served_model_name or '-'}")
    print(f"host: {profile.host}")
    print(f"port: {profile.port}")
    print(f"attention_backend: {profile.attention_backend or '-'}")
    print(f"notes: {profile.notes or '-'}")
    if profile.env:
        print("env:")
        for key, value in sorted(profile.env.items()):
            print(f"  {key}={value}")
    if profile.extra_args:
        print("extra_args:")
        for item in profile.extra_args:
            print(f"  {item}")
    return 0


def _render_profile(config_path: Path, profile_name: str, as_json: bool) -> int:
    plan = build_launch_plan(profile_name, config_path)
    if as_json:
        payload = {
            "profile": plan.profile.name,
            "command": plan.command,
            "env": {key: plan.env[key] for key in sorted(plan.profile.env)},
        }
        print(json.dumps(payload, indent=2))
    else:
        print(plan.shell_command())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        for name in profile_names(args.config):
            print(name)
        return 0
    if args.command == "show":
        return _print_profile(args.config, args.profile)
    if args.command == "render":
        return _render_profile(args.config, args.profile, args.json)
    if args.command == "serve":
        if args.dry_run:
            return _render_profile(args.config, args.profile, False)
        return run_profile(args.profile, args.config)
    if args.command == "version":
        print(__version__)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
