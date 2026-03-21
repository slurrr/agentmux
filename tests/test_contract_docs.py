from pathlib import Path


def test_agents_contract_mentions_mux_primary_product() -> None:
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "assets are not optional decoration" in text
    assert "dead metadata" in text
    assert "compose agent-serving stacks and launch them as real `vllm serve` commands" in text


def test_mux_compiler_spec_exists() -> None:
    text = Path("docs/specs/003-mux-compiler-contract.md").read_text(encoding="utf-8")
    assert "assets.chat_template" in text
    assert "assets.tokenizer" in text
    assert "Silent overlap is not allowed" in text


def test_decisions_capture_anti_drift_rules() -> None:
    decisions = [
        Path("docs/decisions/0002-mux-composition-is-the-product.md"),
        Path("docs/decisions/0003-assets-are-operational.md"),
        Path("docs/decisions/0004-precedence-and-naming-must-be-explicit.md"),
    ]
    for decision in decisions:
        assert decision.exists(), decision
