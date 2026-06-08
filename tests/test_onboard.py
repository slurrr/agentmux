from __future__ import annotations

from pathlib import Path

from agentmux.config import resolve_stack
from agentmux.onboard import OnboardRoots, onboard_model


def _make_hf_cache_root(tmp_path: Path) -> Path:
    cache_root = tmp_path / "models" / "hf" / "hub" / "models--Qwen--Qwen3.5-9B"
    snapshot = cache_root / "snapshots" / "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
    snapshot.mkdir(parents=True)
    (cache_root / "refs").mkdir(parents=True, exist_ok=True)
    (cache_root / "refs" / "main").write_text(
        "c202236235762e1c871ad0ccb60c8ee5ba337b9a\n", encoding="utf-8"
    )
    (snapshot / "config.json").write_text("{}\n", encoding="utf-8")
    return cache_root


def test_onboard_model_creates_links_and_mux_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source = _make_hf_cache_root(tmp_path)
    roots = OnboardRoots(
        model_root=tmp_path / "models",
        local_model_root=tmp_path / "models" / "local" / "hf-snapshots",
        active_model_root=tmp_path / "models" / "active",
        model_manifest_root=tmp_path / "models" / "manifests",
        onboarding_root=tmp_path / "runs" / "agentmux" / "onboarding",
    )
    mux_root = tmp_path / "mux"
    (mux_root / "lab").mkdir(parents=True)

    result = onboard_model(
        source,
        instructions="include memory",
        services=["memory"],
        launch=False,
        smoke=False,
        bench=False,
        roots=roots,
        mux_root=mux_root,
    )

    local_link = Path(result.local_model_path)
    active_link = Path(result.active_model_path)
    manifest = Path(result.manifest_path)
    model_manifest = Path(result.model_manifest_path)

    assert result.slug == "qwen3.5-9b"
    assert local_link.is_symlink()
    assert active_link.is_symlink()
    assert local_link.resolve() == source / "snapshots" / "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
    assert active_link.resolve() == (
        source / "snapshots" / "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
    )
    assert manifest.exists()
    assert model_manifest.exists()

    stack = resolve_stack(result.stack_name, root=mux_root)
    assert stack.track == "lab"
    assert stack.services["main"].model == str(local_link)
    assert stack.services["main"].assets.values["chat_template"] == (
        "assets/chat_templates/qwen3.5_hf_fix_chat_template.jinja"
    )
    assert stack.services["main"].args["max_num_seqs"] == 36
    assert "memory" in stack.services
    assert stack.services["memory"].llm_service == "main"
    assert "include memory" in manifest.read_text(encoding="utf-8")


def test_onboard_model_uses_minimal_gemma_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "models" / "hf" / "hub" / "models--google--Gemma-4-12B-it"
    snapshot = source / "snapshots" / "1111111111111111111111111111111111111111"
    snapshot.mkdir(parents=True)
    (source / "refs").mkdir(parents=True, exist_ok=True)
    (source / "refs" / "main").write_text("1111111111111111111111111111111111111111\n", encoding="utf-8")
    (snapshot / "config.json").write_text("{}\n", encoding="utf-8")

    roots = OnboardRoots(
        model_root=tmp_path / "models",
        local_model_root=tmp_path / "models" / "local" / "hf-snapshots",
        active_model_root=tmp_path / "models" / "active",
        model_manifest_root=tmp_path / "models" / "manifests",
        onboarding_root=tmp_path / "runs" / "agentmux" / "onboarding",
    )
    mux_root = tmp_path / "mux"
    (mux_root / "lab").mkdir(parents=True)

    result = onboard_model(
        source,
        launch=False,
        smoke=False,
        bench=False,
        roots=roots,
        mux_root=mux_root,
    )

    manifest = Path(result.manifest_path)
    stack = resolve_stack(result.stack_name, root=mux_root)
    assert stack.services["main"].model == result.local_model_path
    assert stack.services["main"].args["load_format"] == "auto"
    assert stack.services["main"].args["max_num_seqs"] == 8
    assert "enable_auto_tool_choice" not in stack.services["main"].args
    assert "# Optional Gemma knobs kept commented out for first boot:" in manifest.read_text(encoding="utf-8")
    assert "# enable_auto_tool_choice = true" in manifest.read_text(encoding="utf-8")
    assert "# structured_outputs_config =" in manifest.read_text(encoding="utf-8")


def test_onboard_model_handles_gguf_models(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_root = tmp_path / "models" / "hf" / "hub" / "models--unsloth--gemma-4-31B-it-GGUF"
    snapshot = source_root / "snapshots" / "3f07b20fc8e73cec677713305971e534fe8c4ce3"
    snapshot.mkdir(parents=True)
    (source_root / "refs").mkdir(parents=True, exist_ok=True)
    (source_root / "refs" / "main").write_text(
        "3f07b20fc8e73cec677713305971e534fe8c4ce3\n", encoding="utf-8"
    )
    (snapshot / "gemma-4-31B-it-UD-Q3_K_XL.gguf").write_text("gguf-model", encoding="utf-8")
    (snapshot / "mmproj-BF16.gguf").write_text("gguf-mmproj", encoding="utf-8")

    roots = OnboardRoots(
        model_root=tmp_path / "models",
        local_model_root=tmp_path / "models" / "local" / "hf-snapshots",
        active_model_root=tmp_path / "models" / "active",
        model_manifest_root=tmp_path / "models" / "manifests",
        onboarding_root=tmp_path / "runs" / "agentmux" / "onboarding",
    )
    mux_root = tmp_path / "mux"
    (mux_root / "lab").mkdir(parents=True)

    result = onboard_model(
        source_root,
        stack_name="gemma-4-31b-it-gguf",
        services=[],
        launch=False,
        smoke=False,
        bench=False,
        roots=roots,
        mux_root=mux_root,
    )

    manifest = Path(result.manifest_path)
    assert Path(result.local_model_path).suffix == ".gguf"
    assert Path(result.local_model_path).is_symlink()
    assert Path(result.active_model_path).is_symlink()
    assert Path(result.active_model_path).resolve().suffix == ".gguf"
    stack = resolve_stack(result.stack_name, root=mux_root)
    assert stack.services["main"].model == result.local_model_path
    assert stack.services["main"].args["load_format"] == "gguf"
    assert stack.services["main"].args["dtype"] == "auto"
    assert stack.services["main"].args["tokenizer"] == (
        "/home/poop/models/local/hf-snapshots/gemma-4-e4b-it/current"
    )
    assert stack.services["main"].runtime_bin_dir == "scripts/gemma4-vllm-bin"
    assert "tool_chat_template_gemma4.jinja" in manifest.read_text(encoding="utf-8")
