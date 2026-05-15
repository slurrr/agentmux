# Current Goal
Keep onboarding aligned with the repo’s mux shapes and get a Gemma stack running cleanly.

# Current State
- Onboarding still has the family-aware presets and GGUF file symlink handling in `src/agentmux/onboard.py`.
- The live Gemma stack was switched off the unsupported GGUF artifact and is now using the supported HF snapshot at `/home/poop/models/local/hf-snapshots/gemma-4-e4b-it/current`.
- `mux/lab/gemma-4-31b-it-gguf.toml` currently runs as a Gemma4-E4B memory stack with:
  - `runtime_bin_dir = ".venv-vllm/bin"`
  - `served_model_name = "gemma-4-e4b-memory"`
  - `max_model_len = 65536`
  - `dtype = "bfloat16"`
  - memory service enabled
- `agentmux up gem-mem` now starts successfully and both services are up:
  - LLM on `http://127.0.0.1:8002/v1`
  - Hindsight memory on `http://127.0.0.1:8888/v1`
- The GGUF Gemma 4 path was tested and ruled out: vLLM failed in the GGUF loader with `Unknown gguf model_type: gemma4` and then tensor-map mismatches.
- Validation still passes for the onboarding tests.

# Decisions
- For HF snapshots, keep the stable `current` directory pointer pattern.
- GGUF artifacts can be onboarded as file symlinks, but Gemma 4 GGUF is not a viable serving target in this vLLM stack.
- The working Gemma stack should use the supported HF snapshot instead of forcing the unsupported GGUF artifact.
- Match the mux presets the user hand-tuned instead of keeping the old generic onboarding defaults.
- Use the existing chat template assets already in the repo instead of inventing new template files.

# Open Problems
- Decide whether onboarding should reject Gemma 4 GGUF up front or keep a best-effort experimental path.
- The broader bench-show expectation mismatch in `tests/test_main.py` still exists but is unrelated.

# Resume Instructions
1. If the user wants to keep iterating on Gemma, decide whether to formalize the HF-backed `gem-mem` stack as the default path.
2. If we keep the GGUF experiment around, teach onboarding to fail fast or mark Gemma 4 GGUF as unsupported instead of generating a misleading launch config.
3. If needed, inspect `~/runs/agentmux/logs/20260512-224546-gem-mem-llm.log` for the successful HF launch details.
