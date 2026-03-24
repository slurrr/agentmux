from pathlib import Path
from unittest.mock import Mock, patch

from agentmux.runner import build_stack_plan, launch_stack
from agentmux.runtime import RuntimeService, RuntimeStack, read_active, runtime_status, write_active


def test_build_stack_plan_renders_vllm_command() -> None:
    plan = build_stack_plan("example_vllm_recipes")
    service = plan.services[0]
    assert service.command[:4] == ["uv", "run", "vllm", "serve"]
    assert "${MODEL_ROOT}" not in " ".join(service.command)
    assert service.command[4].endswith("/Qwen2.5-7B-Instruct")
    assert "--chat-template" in service.command
    assert "assets/chat_templates/qwen25_default.jinja" in service.command
    assert "--enable-prefix-caching" in service.command
    assert "--attention-backend" in service.command
    assert "FLASH_ATTN" in service.command
    assert plan.stack.env["CUDA_VISIBLE_DEVICES"] == "0"


def test_build_stack_plan_handles_multi_service_stack() -> None:
    plan = build_stack_plan("example_two_service")
    assert len(plan.services) == 2
    assert {service.service for service in plan.services} == {"router_default", "coder"}
    router_default = next(
        service for service in plan.services if service.service == "router_default"
    )
    assert "--swap-space" in router_default.command
    assert "0" in router_default.command
    assert "--disable-log-requests" in router_default.command


def test_build_stack_plan_assets_override_same_name_args(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mux_root = tmp_path / "mux" / "lab"
    mux_root.mkdir(parents=True)
    (tmp_path / ".env").write_text("MODEL_ROOT=/models\n", encoding="utf-8")
    (mux_root / "collision.toml").write_text(
        """
[stack]
name = "collision"
track = "lab"
primary_service = "main"

[defaults.assets]
chat_template = "assets/chat_templates/from_defaults.jinja"

[services.main]
engine = "vllm"
model = "${MODEL_ROOT}/Qwen/Test"
port = 8000

[services.main.args]
chat_template = "assets/chat_templates/from_args.jinja"

[services.main.assets]
chat_template = "assets/chat_templates/from_assets.jinja"
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_stack_plan("collision", root=tmp_path / "mux")
    command = plan.services[0].command
    assert command.count("--chat-template") == 1
    assert "assets/chat_templates/from_assets.jinja" in command
    assert "assets/chat_templates/from_args.jinja" not in command
    assert "assets/chat_templates/from_defaults.jinja" not in command


@patch("agentmux.runner.subprocess.Popen")
def test_launch_stack_writes_runtime_state(mock_popen, tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mux").symlink_to(repo_root / "mux")
    process = Mock()
    process.pid = 4242
    mock_popen.return_value = process

    runtime_stack = launch_stack("example_vllm_recipes", root=tmp_path / "mux")
    active = read_active()

    assert runtime_stack.stack == "example_vllm_recipes"
    assert active is not None
    assert active.stack == "example_vllm_recipes"
    status = runtime_status(active)
    assert status["stack"] == "example_vllm_recipes"
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

    runtime_stack = launch_stack("example_vllm_recipes", root=tmp_path / "mux")

    assert mock_pid_is_running.called
    assert runtime_stack.stack == "example_vllm_recipes"
