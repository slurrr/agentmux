# Spec: onboarding new models

## Problem

Bringing a new model into the local agent stack is still too manual.

Today the operator has to do several separate things:
- find the model in the Hugging Face cache
- create a stable local pointer to it
- write a new mux manifest with reasonable defaults
- decide whether to include supporting services like Hindsight
- launch the stack and check whether it actually works
- capture at least one evaluation result so the model is not just "installed" but usable

The repo needs a repeatable onboarding path that turns those steps into one predictable workflow.

## Scope

Build a model onboarding process that:
- accepts a source model path from the HF cache or another local snapshot directory
- creates a stable local symlink in the machine model store
- creates a mux manifest with standard-ish defaults
- optionally includes requested supporting services
- launches the stack when possible
- runs a lightweight evaluation automatically
- records onboarding artifacts in a durable run directory

The onboarding workflow should be usable both as:
- a CLI command
- a thin script wrapper for manual or agent-driven use

## Requirements

### 1. Source model handling

- The onboarding process must accept a local path to a model source.
- If the source path is a Hugging Face cache repo root, the workflow must resolve it to a usable snapshot.
- The workflow must create a stable symlink under the local model store.
- The workflow must avoid copying large model files.

### 2. Local model placement

Preferred shape:
- durable local home under `~/models/local/hf-snapshots/<slug>/current`
- active pointer under `~/models/active/<slug>`

The mux manifest should point at the stable local pointer, not at the raw HF cache path.

### 3. Manifest generation

The onboarding process must generate a mux manifest under `mux/lab/` by default.

The manifest should use defaults that match the repo's actual serving style:
- `vllm` as the primary engine for the model service
- sensible `bfloat16` / concurrency / prefix-caching defaults
- model-family-specific tool/chat-template defaults when appropriate
- optional Hindsight service when requested

The generated manifest must be immediately renderable by `agentmux render`.

### 4. Supporting services

The workflow should allow requested services to be included in the generated mux.

Initial supported services:
- `memory` / Hindsight sidecar

### 5. Evaluation

The onboarding workflow must perform at least one evaluation step after the mux is created.

Minimum evaluation:
- launch the stack when possible
- run a smoke check against the OpenAI-compatible endpoint

Optional deeper evaluation:
- run the existing benchmark profile and store the result file

### 6. Artifacts

The workflow must write durable onboarding artifacts, at minimum:
- the generated mux manifest path
- the resolved source model path
- the symlinked local model path
- a short onboarding summary file
- any smoke or benchmark results that were produced

### 7. Non-destructive behavior

- The workflow must not overwrite existing local model pointers or manifests unless explicitly forced.
- If the target stack is already active, the workflow should report that state instead of silently clobbering it.

## Constraints

- Keep the implementation simple and repo-local.
- Do not copy model weights into the repo.
- Do not invent new top-level machine homes.
- Keep the generated mux human-readable.
- Treat the onboarding process as a real stack-creation workflow, not just metadata generation.

## Acceptance Criteria

- A user can point the onboarding command at an HF cache model path and get a stable local symlink.
- The command generates a mux manifest with sensible defaults.
- The command can include a requested Hindsight service.
- The command produces at least a smoke evaluation result.
- Optional deeper benchmark evaluation is available.
- The onboarding artifacts are written to a durable location under `~/runs/agentmux/` and/or `~/models/manifests/`.
- `agentmux render <new-stack>` shows a real launch command immediately after onboarding.
