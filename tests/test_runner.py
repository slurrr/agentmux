from pathlib import Path

from agentmux.runner import build_mux_plan


def test_build_mux_plan_renders_exact_podman_command(tmp_path: Path) -> None:
    mux_dir = tmp_path / "core"
    mux_dir.mkdir(parents=True)
    (mux_dir / "demo.toml").write_text(
        """
[mux]
name = "demo"

[defaults]
podman_args = ["--security-opt", "label=disable", "--device", "nvidia.com/gpu=all"]

[defaults.env]
HF_HOME = "/models/hf"

[defaults.labels]
owner = "agentmux"

[[defaults.volumes]]
source = "~/models"
target = "/models"
mode = "ro"

[services.main]
image = "localhost/llm-demo:latest"
container_name = "agentmux-demo-main"
port = 8002
ports = ["8002:8002"]
command = ["backend", "--serve"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_mux_plan("demo", root=tmp_path)
    command = plan.services[0].command

    assert command[:6] == [
        "podman",
        "run",
        "--detach",
        "--replace",
        "--name",
        "agentmux-demo-main",
    ]
    assert "--device" in command
    assert "nvidia.com/gpu=all" in command
    assert ["--env", "HF_HOME=/models/hf"] == command[
        command.index("--env") : command.index("--env") + 2
    ]
    assert ["--publish", "8002:8002"] == command[
        command.index("--publish") : command.index("--publish") + 2
    ]
    assert command[-3:] == ["localhost/llm-demo:latest", "backend", "--serve"]
    assert plan.services[0].health_url == "http://127.0.0.1:8002/v1/models"
