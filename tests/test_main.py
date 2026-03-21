import json

from agentmux.main import main


def test_render_outputs_stack_commands(capsys) -> None:
    rc = main(["render", "example_vllm_recipes"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "[generalist] uv run vllm serve" in captured.out


def test_show_json_outputs_generic_args(capsys) -> None:
    rc = main(["show", "example_vllm_recipes", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert payload["services"]["generalist"]["args"]["attention_backend"] == "FLASH_ATTN"


def test_list_outputs_track_prefixed_stacks(capsys) -> None:
    rc = main(["list", "--include-archive"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "archive/example_vllm_recipes" in captured.out
    assert "archive/example_two_service" in captured.out
