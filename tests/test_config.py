from pathlib import Path

from agentmux.config import load_profile, profile_names


def test_profile_names_are_sorted() -> None:
    names = profile_names(Path("agentmux.toml"))
    assert names == sorted(names)
    assert "qwen2_5_7b" in names


def test_load_profile_merges_defaults() -> None:
    profile = load_profile("qwen2_5_7b", Path("agentmux.toml"))
    assert profile.model == "Qwen/Qwen2.5-7B-Instruct"
    assert profile.port == 8000
    assert profile.tensor_parallel_size == 1
    assert profile.attention_backend == "FLASH_ATTN"
