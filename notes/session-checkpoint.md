# Current Goal
Make onboarding produce a minimal, runnable Gemma stack without changing the runtime environment.

# Current State
- `src/agentmux/onboard.py` now writes Gemma manifests with a minimal first-boot arg set and comments out risky Gemma-specific knobs.
- Onboarded Gemma manifests now point at the stable local snapshot path (`~/models/local/hf-snapshots/.../current`) instead of the active symlink.
- `mux/lab/gemma-12b-block.toml` was updated to the minimal first-run shape and now uses the local model path.
- `tests/test_onboard.py` was updated for the new path choice and commented Gemma knobs.
- Focused tests pass: `tests/test_main.py::test_render_outputs_stack_commands`, `tests/test_onboard.py`, `tests/test_runner.py`.
- No runtime environment changes were made.

# Decisions
- Keep the model path in manifests on the stable local pointer, not the active symlink.
- For Gemma onboarding, keep the base stack minimal and comment out advanced tool/structured-output knobs until the stack boots.
- Do not change the vLLM/transformers environment yet.

# Open Problems
- `gemma-12b-block` is still based on a `gemma4_unified` artifact, which may remain unsupported in the current vLLM/transformers env.
- The unrelated `bench-show` test failure still exists.

# Resume Instructions
1. If the next step is runtime work, decide whether to stop at the repo-level manifest cleanup or revisit environment support for `gemma4_unified`.
2. If the next step is validation, run `uv run pytest tests/test_main.py::test_render_outputs_stack_commands tests/test_onboard.py tests/test_runner.py -q`.
