#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agentmux.onboard import OnboardingError, onboard_model, render_onboard_summary  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Onboard a new local model into agentmux")
    parser.add_argument("source", type=Path, help="HF cache path or snapshot directory")
    parser.add_argument("--name", help="Optional stack/model slug")
    parser.add_argument(
        "--track",
        default="lab",
        choices=["core", "lab", "bench", "archive"],
        help="Mux track for the generated manifest",
    )
    parser.add_argument(
        "--instructions",
        help="Freeform onboarding instructions to record in the manifest",
    )
    parser.add_argument(
        "--service",
        action="append",
        choices=["memory"],
        default=[],
        help="Add an extra service to the generated mux (repeatable)",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Do not try to launch the generated stack",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip the smoke evaluation step",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Run the benchmark profile after onboarding",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pointers/manifests if needed",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
