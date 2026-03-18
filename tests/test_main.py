from agentmux.main import main


def test_render_outputs_stack_commands(capsys) -> None:
    rc = main(["render", "qwen2_5_7b"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "[generalist] uv run vllm serve Qwen/Qwen2.5-7B-Instruct" in captured.out


def test_list_outputs_track_prefixed_stacks(capsys) -> None:
    rc = main(["list", "--include-archive"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "core/qwen2_5_7b" in captured.out
    assert "archive/example_two_service" in captured.out
