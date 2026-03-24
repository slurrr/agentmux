# Codex CLI + vLLM Responses: Lessons Learned

Date: 2026-03-21
Updated: 2026-03-24

## Purpose
This note captures what was tried to run Codex CLI and later OpenCode against local vLLM via the OpenAI-compatible Responses path, what failed, what partially worked, and what the next targeted attempts should be.

## Current Baseline
This document is historical context. The active repo baseline for OpenCode + OmniCoder is now the direct path:
- OpenCode -> `http://127.0.0.1:8002/v1`
- no local Responses adapter/proxy in the configured request path
- proxy experiments remain in-repo as reference only until explicitly removed

## Stack Under Test
- client: Codex CLI first, then OpenCode
- backend: local vLLM serving OmniCoder / Qwen-family model variants
- API surface: OpenAI-compatible `Responses` endpoint
- comparison baseline: `chat/completions` worked materially better than `Responses`

## What We Tried
- Added a local `/v1/responses` proxy in `src/agentmux/codex_responses_proxy.py`.
- Added `/v1/models` passthrough.
- Added `/v1/models/{model_id}` passthrough plus fallback from list models.
- Added payload normalization:
  - assistant message item field normalization (`id`, `status`, `annotations`, `logprobs`)
  - `developer` -> `system` role mapping
  - system message reordering to front
  - optional deterministic tool-choice forcing
  - optional parallel tool-call disabling
- Added debug observability:
  - request shape plus tool list plus input previews
  - upstream response shape
  - SSE counters for `function_call`, `<tool_call>`, and `output_text`
- Tried both parser modes in mux:
  - `tool_call_parser = "hermes"`
  - `tool_call_parser = "qwen3_xml"`
- Removed custom chat template override to test tokenizer default template.
- Added retry heuristics in proxy for known failures:
  - 400 role/template errors
  - XML tool tags without structured `function_call` events
- Ran repeated OpenCode probes with:
  - direct `opencode run`
  - `--print-logs`
  - exported session inspection
  - proxy log inspection
  - backend log inspection

## What Worked
- Local stack served and responded reliably for plain prompts.
- `chat/completions` behavior was materially better than `Responses`.
- Tool-call path was proven at least sometimes:
  - upstream SSE contained valid structured `function_call`
  - `qwen3_xml` was the best parser of the tried options in this setup
- Proxy-level metadata endpoints became functional.

## Failure Modes
### 1. Model Identity / Metadata Friction
- Client warning persisted: `Model metadata for OmniCoder-9B not found`.
- Proxy endpoints were fixed, but warning still appeared intermittently.
- This looked like client-side fallback or caching behavior more than the core blocker.

### 2. Template / Role Incompatibility
- Upstream 400 errors from template rendering included:
  - `Unexpected message role.`
  - `System message must be at the beginning.`
- This pointed to a strict template contract that did not match the raw Responses payload shape being sent by the client.

### 3. Mixed Tool Output Styles
- The same request could produce:
  - structured `function_call` events
  - XML `<tool_call>` text in assistant output
  - pure text with no structured call under `tool_choice=auto`
- This made tool behavior non-deterministic even when the backend was obviously trying to use tools.

### 4. Broken Streaming
- Codex/OpenCode use SSE for Responses.
- During proxy-based attempts, the stream sometimes failed with incomplete-body / chunked-read style errors.
- This meant proxy normalization could move the request past role errors but still fail during streaming.

### 5. Empty Streaming
- In a later OpenCode iteration, the proxy repeatedly logged:
  - `status_code: 200`
  - `content_type: text/event-stream`
  - `body_bytes: 0`
- This was worse than a clean 400 because the transport looked successful while the semantic response was empty.

### 6. Client Loop / Unknown-Step Churn
- Exported OpenCode sessions for failed runs showed long repeated sequences of:
  - `step-start`
  - `step-finish`
  - `reason: "unknown"`
- That indicated the client was not receiving a valid completed tool turn even when the transport path stayed alive.
- The user-visible symptoms in the same phase included:
  - `Tool execution aborted`
  - `"text part ... not found"`

## Why This Was Hard
This path combined four independent contracts that could disagree:
- Codex/OpenCode Responses payload contract
- proxy adaptation contract
- vLLM Responses API contract
- model/template tool-calling contract

When these drifted even slightly across roles, ordering, tools, parser choice, or stream semantics, behavior degraded from deterministic tool calls into:
- 400 preprocess failures
- mixed XML plus structured output
- broken SSE streams
- empty SSE streams
- client-side loop churn with `reason: "unknown"`

## Later OpenCode Addendum
After the initial proxy iterations, a later pass focused on the exported OpenCode session and local OpenCode package internals rather than rerunning the full stack.

That pass added two important conclusions:
- the literal `text part ... not found` string was not easy to locate statically in the local OpenCode source tree, so it may be produced dynamically rather than existing as a simple constant in the installed package
- the exported failed session looked less like a clean tool-call failure and more like the client repeatedly entering and exiting steps without ever landing a valid tool result

In other words, by the end of the OpenCode follow-up, the failure had progressed through three distinct phases:
1. request-shape rejection at the template layer
2. malformed or incomplete SSE streaming
3. accepted but effectively empty SSE streaming that led to client-side step churn

## Recommended Robust Solution
Use one strict adapter mode rather than heuristic retries if an adapter is still needed.

### Strict Adapter Contract
1. Normalize incoming payload to a canonical internal shape.
- Single top-level `instructions` string.
- `input` contains only supported roles: `user`, `assistant`, `tool`.
- No `developer` or extra `system` messages in `input`.

2. Canonicalize tools to one schema accepted by the backend.

3. Enforce deterministic tool policy.
- If tools are present, use explicit behavior such as `required` or an explicit per-turn override.
- If no structured tool call is emitted, fail explicitly rather than silently falling back.

4. Preserve streaming discipline.
- Preserve SSE framing exactly.
- Do not rewrite stream contents until the baseline path is proven.
- Only consider redacting XML or assistant filler text after the raw stream is already known-good.

5. Return clear failure semantics.
- Return explicit adapter error payloads with reason and normalization summary when the contract cannot be met.

### Why This Is Better
- Fewer moving parts than template-plus-parser-plus-retry guessing.
- Easier to test and reason about.
- More reusable across clients and models.

## Suggested Next Attempts
These are ordered by what should be tried first, then next.

### 1. First Try
Bypass the proxy and reproduce with a minimal direct `/v1/responses` bakeoff against vLLM 0.18.0 using the exact OpenCode payload shape, but outside OpenCode first.

Reason:
- too many moving parts are currently entangled
- this isolates whether vLLM itself can return a non-empty streaming tool-call response for this model
- the bakeoff should be minimal and deterministic:
  - no `developer` role
  - `parallel_tool_calls=false`
  - one simple tool such as `read`
  - explicit tool choice

### 2. Next Try
If direct bakeoff fails, fix the model/template contract before touching client behavior again.

Reason:
- the strongest evidence still points to a shape/template mismatch first
- test the smallest viable template adjustments only:
  - no `developer` role
  - one leading `system` message or top-level instructions only
  - one tool
  - deterministic tool choice
  - no parallel tool calls

### 3. Third Try
If direct bakeoff works, build the thinnest possible adapter and stop rewriting SSE.

Reason:
- the current proxy became part of the instability surface
- the next adapter should only:
  - normalize roles and ordering
  - force deterministic tool knobs
  - pass bytes through untouched
  - log raw upstream frames
- no sanitizing, no retries, no stream mutation until the baseline works

## Practical Decision
For this repo session, continuing Codex CLI compatibility iteration was stopped.

The practical direction became:
- keep the direct OpenCode -> vLLM baseline as the repo default
- keep proxy work in-repo as reference only
- use targeted direct Responses bakeoffs to determine whether the remaining blocker is:
  - vLLM Responses behavior
  - model/template behavior
  - or OpenCode client expectations
