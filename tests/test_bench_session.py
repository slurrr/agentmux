import json
from pathlib import Path

from agentmux.bench_session import DEFAULT_REPO, run_bench_session
from agentmux.main import main


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_bench_session_defaults_repo_path() -> None:
    assert str(DEFAULT_REPO).endswith("/code/bench/bench-playground")


def test_bench_session_runs_and_cleans_worktree(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    (source / ".git").mkdir()
    (source / "README.md").write_text("hello\n", encoding="utf-8")

    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    monkeypatch.setattr("agentmux.bench_session.resolve_stack", lambda stack_name, root: object())
    monkeypatch.setattr("agentmux.bench_session._which_or_error", lambda binary: f"/usr/bin/{binary}")

    def fake_run(cmd, **kwargs):
        cmd0 = cmd[0]
        if cmd0 == "git" and cmd[1] == "clone":
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            (Path(cmd[-1]) / ".git").mkdir(exist_ok=True)
            return _FakeCompleted(0, "", "")
        if cmd0 == "git" and cmd[1] == "status":
            return _FakeCompleted(0, "", "")
        if cmd0 == "git" and cmd[1] == "rev-parse":
            return _FakeCompleted(0, "deadbeef\n", "")
        if cmd0 == "git" and cmd[1] == "log":
            return _FakeCompleted(0, "deadbeef init\n", "")
        if cmd0 == "git" and cmd[1] == "diff":
            return _FakeCompleted(0, "", "")
        if "bwrap" in cmd0:
            return _FakeCompleted(0, "pi output", "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("agentmux.bench_session.subprocess.run", fake_run)

    summary, message = run_bench_session("stack", Path("/tmp"), repo=source)

    assert "bench-session ok" in message
    assert summary["cleanup_performed"] is True
    session_root = Path(summary["session_root"])
    assert (session_root / "session.json").exists()
    assert (session_root / "worktree").exists() is False


def test_main_bench_session_dispatch(monkeypatch, capsys) -> None:
    def fake_run(stack, root, repo, offline, preserve):
        return ({"ok": True}, "bench-session ok: demo")

    monkeypatch.setattr("agentmux.main.run_bench_session", fake_run)

    rc = main(["bench-session", "demo-stack"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "bench-session ok: demo" in out
