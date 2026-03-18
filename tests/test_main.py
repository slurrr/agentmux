from agentmux.main import main


def test_render_dry_run(capsys) -> None:
    rc = main(["render", "qwen2_5_7b"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "uv run vllm serve Qwen/Qwen2.5-7B-Instruct" in captured.out
