# Sampling Profiles (Agent-Level Defaults)

Goal: run one model stack (one vLLM process, one model load) while still getting different
default sampling behavior per agent or per client integration.

This is useful when:
- your primary frontend can send full OpenAI sampling knobs per request (easy case)
- a secondary frontend (example: OpenClaw) only exposes `temperature` and you still want
  "profiles" like `calm`, `balanced`, `spicy`, etc.

## Ground Rules

- vLLM supports per-request sampling parameters in the OpenAI-compatible request body.
  If your frontend can send them, that is the cleanest path.
- vLLM `generation_config` is server-wide defaults. It cannot provide multiple profiles at
  the same time within one running server.
- You cannot "launch another stack into an already-loaded model" by running another
  `vllm serve` process on a different port. Each `vllm serve` is its own model load.

## Recommended Path: Per-Request Sampling From The Frontend

Treat "sampling profile" as a client concern:
- each agent chooses a default set of knobs
- the agent frontend sends those knobs per request

This keeps one mux per model/asset stack and keeps sampling out of the mux definition.

## Fallback Path For Thin Clients: Profile Proxies

When a client cannot send all the knobs you want, put a tiny OpenAI-compatible proxy in
front of vLLM that injects default sampling parameters.

You run one backend:
- vLLM on `http://127.0.0.1:8002/v1`

And multiple profile ports:
- `http://127.0.0.1:8010/v1` (calm defaults)
- `http://127.0.0.1:8011/v1` (spicy defaults)

Each proxy:
- forwards requests upstream
- merges a profile-specific "defaults" dict into the request body only when a field is not
  already present (explicit request values win)

This gives you "multiple stacks" at the HTTP surface without multiple model loads.

### What Needs To Be Proxied

To support most OpenAI-compatible clients, a profile proxy should implement:
- `POST /v1/chat/completions` (many clients)
- `POST /v1/responses` (Codex/OpenCode-style clients)
- `GET /v1/models` and `GET /v1/models/{id}` passthrough (optional, but reduces client friction)

It must also forward streaming responses faithfully (SSE/chunking). If streaming proxying is
unstable, only use the proxy for non-streaming experiments.

### Which Fields Matter

For vLLM 0.18.0, the server-wide generation defaults path (`generation_config`) and the model
config code path explicitly recognize these sampling keys:
- `repetition_penalty`
- `temperature`
- `top_k`
- `top_p`
- `min_p`
- `max_new_tokens` (mapped to request `max_tokens`)

Other OpenAI-ish knobs may exist, but this list is the safest "profile" surface to start with.

### Current Repo State (What You Can Reuse)

`src/agentmux/codex_responses_proxy.py` exists as a Responses adapter and diagnostic shim.
It currently implements:
- `GET /v1/models`
- `GET /v1/models/{model_id}`
- `POST /v1/responses`

It does not implement `POST /v1/chat/completions`, and it is tuned for role/tool-call
normalization work rather than for being a minimal stable proxy.

If you want to use profile proxies for OpenClaw without changing OpenClaw, you need one of:
- add `POST /v1/chat/completions` forwarding
- or build a separate minimal proxy module dedicated to sampling defaults

## Integrating Proxies Into A mux

Today, `agentmux` only launches `engine = "vllm"` services (`src/agentmux/runner.py` rejects
non-vLLM engines). That means:
- you can run profile proxies out-of-band (manual `uvicorn ...`) and still use mux for vLLM
- if you want proxies declared and launched as part of a mux, `agentmux` needs a second engine
  type (for example `engine = "proxy"`) that launches a Python module under `uvicorn`

This is a repo-level decision: it changes what "a mux" can contain (it would become
"serving stack plus edge shims", not just the backend).

## How This Relates To `generation_config`

Use `generation_config` when you want one server-wide default behavior.

Use profile proxies when you want multiple "default personalities" on one loaded model.

`generation_config` docs in this repo: `mux/README.md`.

