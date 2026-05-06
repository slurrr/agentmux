# Current Goal
Restore the benchmark shape after the accidental reset, keep reasoning separated, and get back to the Phase 2 + thinking-budget state without reintroducing the bench_cases churn.

# Current State
- `src/agentmux/bench_cases.py` was reset back to the Phase 1 shape and the accidental extra constants / `request_max_tokens` / `system_prompt` edits were removed.
- The Phase 2 workspace cases still live in `src/agentmux/bench_workspace.py`.
- The bench code still has the thinking-token split work in place:
  - derived thinking tokens from `completion_tokens - visible_response_tokens`
  - `bench-show` prints per-case `Thinking Tokens: xxxx`
  - summary includes a thinking section
  - `thinking_token_budget = 2048` is sent on bench requests
- The current Qwen3.5 serving stack remains XML-tool oriented with the custom template and reasoning parser.
- `uv run pyright src/agentmux/bench.py src/agentmux/bench_workspace.py src/agentmux/bench_report.py src/agentmux/bench_cases.py src/agentmux/bench_tokens.py` passed after the cleanup.
- `uv run pytest tests/test_bench.py -q` passed after the cleanup.
- `uv run pytest tests/test_main.py -q` also passed.

# Thinking Token Plan
- vLLM 0.20.0 returns `prompt_tokens`, `completion_tokens`, and `total_tokens`, but not a native reasoning-token field.
- Derived thinking tokens are computed from `completion_tokens - visible_response_tokens`.
- The CLI shows an average thinking-token summary after a run and a short `Thinking Tokens: xxxx` line for each case in `bench-show`.
- Bench requests send `thinking_token_budget = 2048` to vLLM.

# Chat Template Notes
- The current working template is `assets/chat_templates/qwen3.5_openai_compat_xml.jinja`.
- It is XML-tool oriented and Qwen3 reasoning oriented:
  - `chat_template = assets/chat_templates/qwen3.5_openai_compat_xml.jinja`
  - `chat_template_content_format = "openai"`
  - `tool_call_parser = qwen3_xml`
  - `reasoning_parser = qwen3`
- The extra benchmark-side parsing for `<think>` tags and nested reasoning content was removed.
- Benchmark extraction now trusts the endpoint shape and uses top-level `content` / `reasoning_content`-style fields only.

# Decisions
- Do not merge thinking into response.
- Preserve thinking separately for diagnostics and replay.
- Keep the current experimental serving combo as XML-oriented, not Hermes-oriented.
- Treat the current Qwen3.5 template setup as the active experiment.
- Keep `bench-show` output to the final answer only.
- Keep thinking capability preserved; do not use template/kwargs changes that disable it just to force final answers.
- Track thinking as a derived field from completion usage plus visible response token counting.
- Keep `bench_cases.py` on the Phase 1 shape unless we explicitly decide to move Phase 2 cases back there.

# Open Problems
- Phase 2 workspace cases are currently only in `bench_workspace.py`; decide whether to move them back into `bench_cases.py` or leave them there.
- Need to keep the launch path hardened because `--launch` had teardown-related failures and resource leaks.

# Teardown / Launch Notes
- There was a real teardown issue when using `--launch`.
- Latest logs showed:
  - `destroy_process_group() was not called before program exit`
  - `resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown`
- I hardened shutdown to try SIGINT first and to reap child processes with `waitpid(..., WNOHANG)` after exit.
- That change was applied to both runtime shutdown and launch-failure teardown paths.

# Resume Instructions
1. If needed, restore the Phase 2 workspace cases into `bench_cases.py`.
2. Re-run the benchmark on the current Qwen3.5 stack.
3. Inspect the new thinking-token summary and per-case thinking lines in `bench-show`.
4. If launch failures recur, inspect the latest teardown logs and decide whether additional cleanup is needed.
