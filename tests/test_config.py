from agentmux.config import list_stacks, resolve_stack


def test_list_stacks_finds_tracks() -> None:
    stacks = list_stacks(include_archive=True)
    names = {stack.name for stack in stacks}
    assert "qwen2_5_7b" in names
    assert "deepseek_r1_qwen_14b" in names
    assert "example_two_service" in names


def test_resolve_stack_parses_services() -> None:
    stack = resolve_stack("qwen2_5_7b")
    assert stack.track == "core"
    assert stack.primary_service == "generalist"
    assert stack.services["generalist"].attention_backend == "FLASH_ATTN"


def test_resolve_stack_supports_multi_service_shape() -> None:
    stack = resolve_stack("example_two_service")
    assert len(stack.services) == 2
    assert stack.primary_service == "router_default"
