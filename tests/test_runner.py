from pathlib import Path

from agentmux.runner import build_launch_plan


def test_build_launch_plan_includes_expected_args() -> None:
    plan = build_launch_plan("deepseek_r1_distill_qwen_14b", Path("agentmux.toml"))
    assert plan.command[:4] == ["uv", "run", "vllm", "serve"]
    assert "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B" in plan.command
    assert "--attention-backend" in plan.command
    assert "FLASH_ATTN" in plan.command
    assert "--gpu-memory-utilization" in plan.command


def test_build_launch_plan_carries_profile_env() -> None:
    plan = build_launch_plan("qwen2_5_7b", Path("agentmux.toml"))
    assert plan.env["PATH"]
    assert plan.env["CUDA_VISIBLE_DEVICES"] == "0"


def test_build_launch_plan_loads_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=from-dotenv\n", encoding="utf-8")
    config_path = tmp_path / "agentmux.toml"
    config_path.write_text(
        """
[defaults]
host = "0.0.0.0"
port = 8000

[profiles.demo]
model = "demo/model"
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_launch_plan("demo", config_path)
    assert plan.env["HF_TOKEN"] == "from-dotenv"
