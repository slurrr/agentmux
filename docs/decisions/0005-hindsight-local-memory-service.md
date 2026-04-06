# 0005: Hindsight runs alongside agentmux as the local memory service

## Status
Accepted

## Context
This machine runs multiple agent frontends (for example, `pi-ghosty`) against a local model backend served via vLLM.

Long-term memory (retain/recall/reflect) is provided by **Hindsight** (vectorize-io/hindsight) via its HTTP API.
Multiple repos may want to use Hindsight with different banks.

We want a single, machine-local Hindsight instance that:
- is easy to run during development
- is compatible with the repo’s preference for Python + `uv`
- can later be promoted to a user-level `systemd` service

`agentmux` is the natural home for this on this machine because:
- it already owns “agent backend services” (vLLM muxes) as a workflow
- it is already a Python repo using `uv`
- it already follows the machine contract of keeping runtime state under `~/runs/...`

## Decision
We run Hindsight from `agentmux` as an **optional stack sidecar**.

- Memory is configured per stack under `[stack.memory]`.
- `provider = "hindsight"` enables memory for that stack.
- `agentmux up` launches Hindsight alongside vLLM services when configured.
- Frontends still integrate via env only:
  - `HINDSIGHT_BASE_URL`
  - `HINDSIGHT_BANK_ID`

Hindsight’s LLM backend settings are derived from the stack primary service and are not user-overridable in `[stack.memory]`.

## Spec
Implementation details live in:
- `docs/specs/004-hindsight-embedded-server.md`

## Consequences
Positive:
- One Hindsight service can serve multiple repos/banks, matching how vLLM is used.
- Avoids Docker and external Postgres complexity during local development.
- Clean upgrade path to a `systemd --user` unit later (the runner script becomes ExecStart).

Tradeoffs:
- Adds one more managed process in stack launches.
- Reuse detection for existing Hindsight is heuristic (HTTP health probe), not identity-perfect.

Follow-ups:
- Promote to `systemd --user` if always-on behavior becomes preferred.
- Add dedicated operator docs if memory manifest surface expands.
