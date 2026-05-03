from pathlib import Path

from agentmux.config import list_stacks, resolve_stack


def test_list_stacks_finds_tracks() -> None:
    stacks = list_stacks(include_archive=True)
    names = {stack.name for stack in stacks}
    assert "qwen3_5_9b" in names
    assert "example_vllm_recipes" in names
    assert "example_two_service" in names


def test_resolve_stack_parses_services() -> None:
    stack = resolve_stack("example_vllm_recipes")
    assert stack.track == "examples"
    assert stack.primary_service == "generalist"
    assert stack.services["generalist"].args["attention_backend"] == "FLASH_ATTN"
    assert stack.services["generalist"].args["enable_prefix_caching"] is True


def test_resolve_stack_supports_multi_service_shape() -> None:
    stack = resolve_stack("example_two_service")
    assert len(stack.services) == 2
    assert stack.primary_service == "router_default"
    assert stack.services["coder"].assets.values["chat_template"] == "assets/chat_templates/coder.jinja"


def test_resolve_stack_supports_bench_track_example() -> None:
    stack = resolve_stack("example_bench_mux")
    assert stack.track == "examples"
    assert stack.services["main"].args["generation_config"] == "vllm"
    assert stack.services["main"].args["max_model_len"] == 8192


def test_resolve_stack_loads_system_prompt_asset() -> None:
    stack = resolve_stack("example_vllm_recipes")
    assert stack.services["generalist"].assets.values["system_prompt"] == "assets/prompts/generalist_system.md"


def test_resolve_stack_supports_hindsight_service_shape() -> None:
    stack = resolve_stack("example_hindsight_memory")
    memory = stack.services["memory"]
    assert memory.engine == "hindsight"
    assert memory.runtime_bin_dir == ".venv-hindsight/bin"
    assert memory.data_dir == str(Path("~/data/hindsight").expanduser())
    assert memory.llm_service == "main"


def test_resolve_stack_expands_env_backed_model_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TEST_MODEL_ROOT=/models\n", encoding="utf-8")
    mux_root = tmp_path / "mux" / "core"
    mux_root.mkdir(parents=True)
    stack_path = mux_root / "local_model.toml"
    stack_path.write_text(
        """
[stack]
name = "local_model"
track = "core"
primary_service = "main"

[services.main]
engine = "vllm"
model = "${TEST_MODEL_ROOT}/Qwen/Test"
port = 8000
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    stack = resolve_stack("local_model", root=tmp_path / "mux")
    assert stack.services["main"].model == "/models/Qwen/Test"


def test_resolve_stack_merges_default_args_and_env() -> None:
    stack = resolve_stack("example_vllm_recipes")
    service = stack.services["reasoner"]
    assert service.args["dtype"] == "bfloat16"
    assert service.args["gpu_memory_utilization"] == 0.92
    assert service.args["attention_backend"] == "FLASH_ATTN"
    assert service.env["CUDA_VISIBLE_DEVICES"] == "1"


def test_resolve_stack_merges_default_assets() -> None:
    stack = resolve_stack("example_vllm_recipes")
    service = stack.services["reasoner"]
    assert service.assets.values["tokenizer"].endswith("/SharedTokenizer")
    assert service.assets.values["chat_template"] == "assets/chat_templates/deepseek_reasoning.jinja"
