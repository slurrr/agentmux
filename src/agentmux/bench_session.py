from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from agentmux.config import resolve_stack
from agentmux.runtime import runtime_root

DEFAULT_REPO = Path.home() / "code" / "bench" / "bench-playground"


class BenchSessionError(RuntimeError):
    pass


def _which_or_error(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise BenchSessionError(f"required binary not found in PATH: {binary}")
    return path


def _session_root(stack_name: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = runtime_root() / "bench-sessions" / f"{stamp}-{stack_name}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_git(worktree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_bwrap_command(worktree: Path, *, offline: bool) -> list[str]:
    pi_path = _which_or_error("pi")
    cmd = [
        _which_or_error("bwrap"),
        "--die-with-parent",
        "--new-session",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/bin",
        "/bin",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(worktree),
        str(worktree),
        "--chdir",
        str(worktree),
    ]
    if offline:
        cmd.extend(["--unshare-net"])
    cmd.extend([pi_path])
    return cmd


def run_bench_session(
    stack_name: str,
    root: Path,
    *,
    repo: Path | None = None,
    offline: bool = False,
    preserve: bool = False,
) -> tuple[dict[str, Any], str]:
    resolve_stack(stack_name, root=root)
    source_repo = (repo or DEFAULT_REPO).expanduser().resolve()

    if not source_repo.exists():
        raise BenchSessionError(f"repo path does not exist: {source_repo}")
    if not (source_repo / ".git").exists():
        raise BenchSessionError(f"repo path is not a git repo: {source_repo}")

    _which_or_error("git")
    _which_or_error("bwrap")
    _which_or_error("pi")

    session_root = _session_root(stack_name)
    worktree = session_root / "worktree"

    _write_text(
        session_root / "preflight.txt",
        "\n".join(
            [
                f"stack={stack_name}",
                f"source_repo={source_repo}",
                f"session_root={session_root}",
                f"offline={offline}",
                f"preserve={preserve}",
            ]
        )
        + "\n",
    )

    clone = subprocess.run(
        ["git", "clone", "--quiet", str(source_repo), str(worktree)],
        capture_output=True,
        text=True,
        check=False,
    )
    if clone.returncode != 0:
        raise BenchSessionError(f"failed to clone repo: {clone.stderr.strip()}")

    baseline_status = _run_git(worktree, "status", "--short")
    _write_text(session_root / "baseline_git_status.txt", baseline_status.stdout)
    baseline_head = _run_git(worktree, "rev-parse", "HEAD")
    _write_text(session_root / "baseline_head.txt", baseline_head.stdout)

    started_at = time.time()
    bwrap_cmd = _build_bwrap_command(worktree, offline=offline)
    stdout_path = session_root / "transcript.stdout.txt"
    stderr_path = session_root / "transcript.stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as out_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_handle:
        pi_run = subprocess.run(
            bwrap_cmd,
            cwd=worktree,
            stdout=out_handle,
            stderr=err_handle,
            text=True,
            check=False,
        )

    status = _run_git(worktree, "status")
    log = _run_git(worktree, "log", "--oneline", "-n", "20")
    diff = _run_git(worktree, "diff")
    _write_text(session_root / "git_status.txt", status.stdout)
    _write_text(session_root / "git_log_oneline.txt", log.stdout)
    _write_text(session_root / "git_diff.patch", diff.stdout)

    summary: dict[str, Any] = {
        "stack": stack_name,
        "source_repo": str(source_repo),
        "session_root": str(session_root),
        "worktree": str(worktree),
        "offline": offline,
        "preserve": preserve,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pi_returncode": pi_run.returncode,
        "sandbox_command": bwrap_cmd,
        "artifacts": {
            "baseline_git_status": str(session_root / "baseline_git_status.txt"),
            "baseline_head": str(session_root / "baseline_head.txt"),
            "transcript_stdout": str(stdout_path),
            "transcript_stderr": str(stderr_path),
            "git_status": str(session_root / "git_status.txt"),
            "git_log_oneline": str(session_root / "git_log_oneline.txt"),
            "git_diff": str(session_root / "git_diff.patch"),
        },
    }

    _write_text(session_root / "session.json", json.dumps(summary, indent=2) + "\n")

    cleanup_performed = False
    keep = preserve or pi_run.returncode != 0
    if not keep:
        shutil.rmtree(worktree, ignore_errors=True)
        cleanup_performed = True

    summary["cleanup_performed"] = cleanup_performed
    summary["kept_session"] = not cleanup_performed
    _write_text(session_root / "session.json", json.dumps(summary, indent=2) + "\n")

    status_word = "ok" if pi_run.returncode == 0 else "failed"
    msg = (
        f"bench-session {status_word}: stack={stack_name} offline={offline} "
        f"cleanup={'yes' if cleanup_performed else 'no'} artifacts={session_root}"
    )
    return summary, msg
