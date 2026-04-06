# Hindsight Memory Plan (agentmux)

Audience: backend implementers/operators.

This document captures the **intended v1 behavior** for running Hindsight as the local memory sidecar, plus the **future direction** we expect to evolve toward.

It is derived from the `pi-ghosty` memory decisions/specs (Hindsight retain/recall/reflect; tags/scopes; CPU-first embeddings; TEI later) and adapted to the `agentmux` “local service” workflow.

## Goals
- Provide a single local Hindsight HTTP API that multiple agent frontends can use.
- Keep GPU VRAM primarily available for **vLLM serving** (24GB constraint).
- Make v1 simple, reproducible, and observable.

## Service Topology
### v1 (now)
- **vLLM**: already hosted/managed via agentmux muxes.
  - OpenAI-compatible base URL (example): `http://127.0.0.1:8002/v1`
- **Hindsight API**: local HTTP service.
  - API: `http://127.0.0.1:8888`
  - (Optional) UI: `http://127.0.0.1:9999` if enabled by Hindsight distribution.

Hindsight is a sidecar: it is not embedded into each agent frontend.

## V1 Behavior Contract
### 1) LLM backend for retain/reflect
- Hindsight needs an LLM for retain/reflect (structured output).
- v1 should point Hindsight at the **same local vLLM endpoint** used by agent frontends.
- Use OpenAI-compatible provider mode (Hindsight side): `openai`.
- API key: if required by the Hindsight server/provider client, use a **dummy key** (vLLM ignores it).

Operational intent:
- Do **not** run a second GPU model just for memory in v1.
- If memory quality is poor, we can later swap Hindsight to a stronger provider/model without changing frontends.

### 2) Retain / Recall / Reflect
- **Recall**: run before each agent turn; inject a bounded memory block into the agent system prompt.
- **Retain**: run after each agent turn.
- **Reflect / observations**:
  - v1 expects observations/consolidation to be enabled (Hindsight-managed), producing durable learnings over time.
  - explicit reflect can be added later (manual / scheduled) without changing the core contract.

### 3) Retention strategy
- v1 retains **full session transcripts** as documents.
- Use stable document ids per agent session so updates are incremental.

### 4) Bank / tags / scopes
- v1 can use a **single bank** for a single-user workstation.
- Isolation comes from tags:
  - `project:<name>` (example: `project:pi-ghosty`)
  - `agent:<role>` (example: `agent:coder`)
  - `session:<id>`

- Observation scopes should consolidate at durable scopes:
  - project scope (`[project:<name>]`)
  - agent scope (`[agent:<role>]`)
  - avoid per-session durable scopes by default (too noisy)

### 5) Frontend contract (clients)
Frontends should only need:
- `HINDSIGHT_BASE_URL` (default: `http://127.0.0.1:8888`)
- `HINDSIGHT_BANK_ID` (repo-specific)

Testing guidance:
- Use a `*-test` bank id (example: `pi-ghosty-test`) during development.
- Reset/delete the test bank after validation.

### 6) Downtime behavior
Frontends should treat Hindsight as optional:
- if Hindsight is down, agent runtime should continue with memory disabled (log/trace the failure).

## VRAM / Embeddings Guidance
### Current issue
If Hindsight is “loading into VRAM”, it is likely pulling GPU-enabled dependencies (embeddings, rerankers, or inference backends) onto CUDA by default.

### v1 intent
- Embeddings and reranking should be **CPU-friendly by default**.
- The GPU should be reserved for vLLM.

### Practical v1 guardrails (implementation knobs)
Implementers should attempt to force CPU execution for non-vLLM parts by configuration, for example:
- run the Hindsight process with `CUDA_VISIBLE_DEVICES=""` (or equivalent) if Hindsight supports CPU-only operation
- choose CPU embeddings models / providers explicitly
- avoid starting any GPU inference engines inside the Hindsight process

Exact knobs depend on Hindsight’s server configuration surface; verify against upstream docs/API.

## Future Direction (post-v1)
### Dedicated embeddings service (TEI)
- Move embeddings generation (and possibly reranking) into a dedicated TEI server process.
- Keep TEI on CPU (or a separate allocation) to avoid contending with vLLM VRAM.
- Agent frontends remain unchanged; only Hindsight’s internal configuration changes.

### Stronger memory LLM (optional)
- If vLLM-served `omnicoder-9b` is insufficient for high-quality retain/reflect, configure Hindsight to use:
  - a different local model (if available), or
  - a remote provider

This should be a server-side change only.

### No-compaction mode
Longer-term goal:
- rely primarily on rolling window context + Hindsight recall injection each turn
- reduce dependence on transcript compaction

This is gated on recall quality and should be validated empirically before adopting.

## Implementation Pointers
- Decision record: `docs/decisions/0005-hindsight-local-memory-service.md`
- Implementation spec: `docs/specs/004-hindsight-embedded-server.md`

This reference doc is intentionally “what we’re trying to achieve”; specs should remain the source of truth for concrete parameters and acceptance tests.
