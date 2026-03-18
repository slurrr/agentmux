from pathlib import Path
from unittest.mock import Mock, patch

from agentmux.runner import build_stack_plan, launch_stack
from agentmux.runtime import RuntimeService, RuntimeStack, read_active, runtime_status, write_active


def test_build_stack_plan_renders_vllm_command() -> None:
    plan = build_stack_plan("qwen2_5_7b")
    service = plan.services[0]
    assert service.command[:4] == ["uv", "run", "vllm", "serve"]
    assert "Qwen/Qwen2.5-7B-Instruct" in service.command
    assert service.env["CUDA_VISIBLE_DEVICES"] == "0"


def test_build_stack_plan_handles_multi_service_stack() -> None:
    plan = build_stack_plan("example_two_service")
    assert len(plan.services) == 2
    assert {service.service for service in plan.services} == {"router_default", "coder"}


@patch("agentmux.runner.subprocess.Popen")
def test_launch_stack_writes_runtime_state(mock_popen, tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mux").symlink_to(repo_root / "mux")
    process = Mock()
    process.pid = 4242
    mock_popen.return_value = process

    runtime_stack = launch_stack("qwen2_5_7b", root=tmp_path / "mux")
    active = read_active()

    assert runtime_stack.stack == "qwen2_5_7b"
    assert active is not None
    assert active.stack == "qwen2_5_7b"
    status = runtime_status(active)
    assert status["stack"] == "qwen2_5_7b"
    assert status["services"][0]["pid"] == 4242


@patch("agentmux.runner.pid_is_running", return_value=False)
@patch("agentmux.runner.subprocess.Popen")
def test_launch_stack_ignores_stale_active_state(
    mock_popen,
    mock_pid_is_running,
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mux").symlink_to(repo_root / "mux")
    write_active(
        RuntimeStack(
            stack="stale",
            track="core",
            path="mux/core/stale.toml",
            services=[
                RuntimeService(
                    name="old",
                    pid=1111,
                    port=8000,
                    command=["uv", "run", "vllm"],
                    log_path=".agentmux/logs/old.log",
                    started_at=1.0,
                )
            ],
            started_at=1.0,
        )
    )
    process = Mock()
    process.pid = 5252
    mock_popen.return_value = process

    runtime_stack = launch_stack("qwen2_5_7b", root=tmp_path / "mux")

    assert mock_pid_is_running.called
    assert runtime_stack.stack == "qwen2_5_7b"
