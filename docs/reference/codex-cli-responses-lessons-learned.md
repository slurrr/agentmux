# Codex CLI + vLLM Responses: Lessons Learned

Date: 2026-03-21

## Scope
This note captures what was tried to run Codex CLI against local vLLM via a Responses proxy, why behavior was unstable, and what a robust model-runner solution should look like.

## What We Tried
- Added a local `/v1/responses` proxy in `src/agentmux/codex_responses_proxy.py`.
- Added `/v1/models` passthrough.
- Added `/v1/models/{model_id}` passthrough + fallback from list models.
- Added payload normalization:
  - assistant message item field normalization (`id`, `status`, `annotations`, `logprobs`)
  - `developer` -> `system` role mapping
  - system message reordering to front
- Added debug observability:
  - request shape + tool list + input previews
  - upstream response shape
  - SSE counters (`function_call`, `<tool_call>`, `output_text` mentions)
- Tried both parser modes in mux:
  - `tool_call_parser = "hermes"`
  - `tool_call_parser = "qwen3_xml"`
- Removed custom chat template override to test tokenizer default template.
- Added retry heuristics in proxy for known failures:
  - 400 role/template errors
  - XML tool tags without structured `function_call` events

## Observed Failure Modes
1. Model identity / metadata friction
- Client warning persisted: `Model metadata for OmniCoder-9B not found`.
- Proxy endpoints were fixed, but warning still appeared intermittently (likely client-side fallback behavior/caching).

2. Template-role incompatibility (hard failures)
- Upstream 400 errors from template rendering:
  - `Unexpected message role.`
  - `System message must be at the beginning.`
- Indicates strict template expectations that differ from Codex Responses payload shape.

3. Mixed tool output styles (soft failures)
- Same request could produce:
  - structured `function_call` events (good)
  - XML `<tool_call>` text in assistant output (bad UX)
  - pure text/no function call under `tool_choice=auto` (non-deterministic)

4. Streaming mismatch risk
- Codex uses SSE for Responses.
- Debugging and adaptation must preserve stream semantics while handling strict template constraints.

## What Actually Worked
- Local stack served and responded reliably for plain prompts.
- Tool-call path was proven at least sometimes:
  - upstream SSE contained valid `function_call` for `exec_command` with `{"cmd":"pwd"}`.
- Proxy-level metadata endpoints became functional.

## Why This Was Hard
This path combines four independent contracts that can disagree:
- Codex Responses payload contract
- proxy adaptation contract
- vLLM Responses API contract
- model/template tool-call contract

When these drift even slightly (roles/order/tools/template/parser), behavior degrades from deterministic tool calls into mixed text/XML or 400 preprocess failures.

## Recommended Robust Solution (Model-Runner)
Use one strict adapter mode rather than heuristic retries.

### Strict Adapter Contract
1. Normalize incoming payload to a canonical internal shape:
- Single top-level `instructions` string.
- `input` contains only supported roles: `user`, `assistant`, `tool`.
- No `developer` or extra `system` messages in `input`.

2. Canonicalize tools to one schema accepted by backend.

3. Deterministic tool policy:
- If tools are present, enforce explicit behavior (`required` or explicit per-turn override).
- If no structured tool call is emitted, fail with explicit adapter error (not silent fallback).

4. Streaming discipline:
- Preserve SSE framing.
- Optionally redact non-actionable assistant XML/thinking text when a valid structured tool call exists.

5. Clear failure semantics:
- Return explicit adapter error payload with reason and normalization summary when contract cannot be met.

### Why This Is Better
- Fewer moving parts than template/parser guessing.
- Easier to test and reason about.
- Works as a reusable runner capability across clients/models.

## Practical Decision
For this repo session, continuing Codex CLI compatibility iteration was stopped.
Next step is to implement strict adapter behavior in model-runner context (or move to OpenCode where client/backend contract is more predictable).

