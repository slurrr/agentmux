# Spec: Initial Backend Cockpit

## Problem
Launching agent-serving backends by hand is error-prone once model stacks, ports, env vars, and
future LoRA attachments start to vary.

## Scope
Build a stack-first CLI that discovers stack manifests from `mux/`, renders launch commands,
launches thin runtime sessions, tracks minimal session metadata, and performs OpenAI-compatible
smoke tests.

## Requirements
- Stack manifests with one or more services
- Separate `core`, `lab`, and `archive` tracks
- Thin process control without a resident service
- OpenAI-compatible smoke testing
- Clear room for future LoRA-first and multi-service evolution

## Constraints
- Single-machine RTX 4090 target for now
- Prefer `uv` and `.venv`
- vLLM is the first engine but not the only possible future engine

## Acceptance Criteria
- `uv run agentmux list --include-archive` discovers stack manifests
- `uv run agentmux render <stack>` prints per-service commands
- `uv run agentmux up <stack>` records runtime metadata
- `uv run agentmux status` reports active stack/service state
- `uv run agentmux smoke <stack>` validates an OpenAI-compatible round-trip
