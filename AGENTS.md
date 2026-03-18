# AGENTS.md

## Project Overview
- Purpose: provide a thin but strong backend cockpit for stack-based model serving
- Primary user: local operator running agent-serving backends on a single RTX 4090 24 GB machine
- Non-goals: housing real agent definitions in v1, building a resident control service, or replacing `vllm`

## Stack Model
- Primary config object: stack
- Stack: one workload topology containing one or more named services
- Service: one serving process, currently usually `vllm serve`
- Boundary: OpenAI-compatible inference endpoints

## Working Agreements
- Keep stack manifests under `mux/core`, `mux/lab`, and `mux/archive`.
- CLI commands are stack-first, with service details only when needed.
- Process control stays thin: launch, stop, inspect, and smoke-test, but do not build a daemon.
- Keep global env minimal and prefer explicit manifest fields over broad vLLM env overrides.
- Add or update tests whenever manifest shape, rendering, runtime state, or smoke behavior changes.

## Commands
- Setup: `uv sync && uv pip install vllm --torch-backend=auto`
- Checks: `./scripts/dev.sh`
- List stacks: `uv run agentmux list --include-archive`
- Render stack: `uv run agentmux render qwen2_5_7b`
- Launch stack: `uv run agentmux up qwen2_5_7b`
- Stop stack: `uv run agentmux down`
- Smoke test: `uv run agentmux smoke qwen2_5_7b --json`

## Conventions
- Proven stacks go in `mux/core`; experiments go in `mux/lab`.
- Archive old stack references instead of deleting them when they remain useful context.
- Keep secrets out of manifests; use `.env` for tokens and machine-specific values.
