# 0001: Stack-First Backend Cockpit

## Status
Accepted

## Context
The repo must stay a clean serving environment rather than becoming another agent playground. It
needs strong operator ergonomics, reproducible stack config, and future room for multiple services
and LoRAs without turning into its own app.

## Decision
Model the repo around stack manifests under `mux/`, where each stack contains one or more named
services. Use a stack-first CLI to render, launch, stop, inspect, and smoke-test those stacks while
letting `vllm` remain the real serving process.

## Consequences
- The repo stays backend-only and OpenAI-compatible at the boundary.
- Runtime metadata is local and file-backed, not daemon-backed.
- Future multi-service and LoRA work can fit the existing stack abstraction.
