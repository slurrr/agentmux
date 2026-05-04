# Current Goal
Make the workspace benchmark replay history the same way Pi does for the active Qwen3.5 serving stack, then re-run the full bench.

# Current State
- Active serving stack now under test:
  - manifest: `mux/bench/qwen3.5_9b.toml`
  - model: `qwen3.5_9b`
  - runtime: `.venv-vllm` / vLLM `0.20.0`
  - template: `assets/chat_templates/qwen3.5_hf_fix_chat_template.jinja`
  - parsers: `tool_call_parser=qwen3_xml`, `reasoning_parser=qwen3`
- Root cause of the 400s is identified:
  - not parser failure
  - not malformed bench messages
  - bench was replaying tool results as JSON blobs in `tool.content`
  - with this template stack, JSON-looking tool-result text gets replay-normalized into a shape the template rejects with `Unexpected content type`
- Pi comparison:
  - Pi keeps richer internal history, but when it sends OpenAI chat-completions payloads it flattens tool results to plain text `role="tool"` messages and keeps assistant tool-call turns as `content=null` plus reasoning/tool_calls.
- Bench replay now matches that shape more closely.
- Local fix implemented in `src/agentmux/bench_workspace.py`:
  - assistant replay tool-call turns use `content=None`
  - replay uses `reasoning` instead of `reasoning_content`
  - tool results are replayed as plain text summaries / file contents, not JSON envelopes
  - `tool` replay messages no longer include `name`
- Verified live against the running server on `http://127.0.0.1:8002/v1`:
  - workspace replay no longer 400s
  - passing cases: `update_api_base_url`, `rename_timeout_key_everywhere_needed`, `add_readme_environment_section`
  - remaining failing workspace case: `ambiguous_production_switch_requires_clarification` (behavioral, not transport/replay)
  - latest ad-hoc workspace stats: `model_requests=15`, `tool_calls=18`, `invalid_tool_calls=0`

# Decisions
- Treat the workspace replay problem as a client-side history-format bug, not a parser bug.
- Align benchmark replay with Pi-style OpenAI completions replay.
- Keep thinking preserved; do not disable thinking to make the benchmark pass.
- Keep tool-result replay human/plain-text, not JSON-structured.

# Open Problems
- Full `agentmux bench` has not been re-run yet after the workspace replay fix.
- No-tool benchmark behavior still needs re-validation under the current template/manifest.
- `ambiguous_production_switch_requires_clarification` still over-edits instead of clarifying.

# Resume Instructions
1. Re-run the full benchmark for `qwen3_5-bench` with the current manifest.
2. Inspect the new benchmark JSON for both `quality_no_tools` and `quality_with_tools`.
3. If only the ambiguous workspace case fails, fix that behavior separately from transport/history replay.
