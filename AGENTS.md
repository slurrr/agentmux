# AGENTS.md

## Role In This Repo
Work with me as a partner, not as an autopilot assistant.

Your job is to:
- help me think
- refine ideas
- surface tradeoffs
- capture decisions clearly
- turn decisions into a concrete spec
- implement the approved plan cleanly

Do not optimize this repo for maximum abstraction, maximum schema control, or generic production-style architecture unless I explicitly ask for that.

## Repo Intent
This repo is a cockpit for composing and launching muxes.

A mux is a human-oriented agent-serving stack that compiles down to a real `vllm serve` command.
The repo exists so I can build, inspect, and launch those commands from organized manifests instead
of hand-composing them every time.

This is a simple project. The job here is not to invent architecture. The job is to make it easy
for a human to compose agent-serving stacks and launch them as real `vllm serve` commands.

A mux can include:
- model target
- backend/runtime args
- chat templates
- LoRAs
- tokenizer-related assets
- prompt assets and other stack parts that make the backend behave like an agent stack

## Hard Boundaries
- `args` are direct backend/runtime `vllm serve` flags.
- assets are not optional decoration. assets are part of the actual mux definition.
- when an asset corresponds to a real `vllm serve` flag, the repo should compile it into that flag.
- if a manifest field exists to describe a real stack part but does not affect launch behavior, treat that as a bug or missing implementation, not as acceptable metadata.
- this repo should be organized around human stack composition, not around reproducing a flat CLI by hand.

## Asset Contract
Treat these as first-class mux parts, not secondary extras:
- chat templates
- tokenizer-related files
- LoRAs
- prompt assets and other files that make the backend behave like an agent stack

The expected behavior is:
- mux fields describe the stack in human terms
- the repo compiles those fields into a real `vllm serve` command
- `render` shows the exact command that will run

## Anti-Drift Rules
Do not do any of the following unless I explicitly ask:
- reframe stack composition as mere sugar or optional convenience
- treat raw `args` as the only real product surface
- leave asset-backed stack fields as passive metadata when they should change launch behavior
- normalize model names, served model names, or stack names unless I explicitly ask
- prefer generic production patterns over the mux workflow used in this repo
- silently choose precedence rules between stack parts; if precedence matters, write it down explicitly
- when precedence is already documented, follow it instead of inventing config errors or new override behavior

This repo is expected to be used from the CLI or from tools like VS Code, with configured agent
frontends sending OpenAI-compatible requests to the running muxes.

## Workflow
1. Planning
- Talk through the high-level idea first.
- Surface tradeoffs, risks, and hidden assumptions.
- Do not rush into implementation while the shape is still unclear.

2. Detail Lock-In
- Work through important details.
- Clarify scope, non-goals, and deferred work.
- Surface meaningful tradeoffs instead of silently deciding them.

3. Spec And Plan
- Write the plan after the thinking is done.
- Reflect what we agreed, not a cleaner architecture you invented.
- I review it.
- We iterate until it is approved.

4. Implementation
- Follow the approved plan.
- Do not quietly redesign during implementation.
- If the plan has a real flaw, stop and surface it clearly.

## Priorities
When in doubt, prefer:
- collaboration over domination
- discussion before action
- explicit decisions before architecture
- simpler structures before stricter schema
- workflow fit over generic best practices
- realistic examples over feature-showcase examples

## Repo Map
Use this map before scanning the codebase.

- `src/agentmux/main.py`: CLI entry point and command surface.
- `src/agentmux/config.py`: manifest loading, env expansion, and typed stack/service parsing.
- `src/agentmux/runner.py`: command construction and stack launch behavior.
- `src/agentmux/runtime.py`: active stack state, history, pid tracking, and log paths.
- `src/agentmux/smoke.py`: OpenAI-compatible smoke checks against running services.
- `mux/`: stack manifests.
  - `mux/core/`: known-good muxes.
  - `mux/lab/`: experimental muxes.
  - `mux/archive/`: reference-only shapes and retired ideas.
  - `mux/README.md`: manifest conventions and supported shapes that are not shown in normal examples.
- `assets/`: small versioned serving assets.
  - `assets/prompts/`: system prompts and prompt fragments.
  - `assets/chat_templates/`: chat templates.
  - `assets/tokenizers/`: tokenizer-related small files.
- `docs/specs/`: concrete requirements before larger features.
- `docs/decisions/`: durable architecture and repo-structure decisions.
- `tests/`: behavior coverage for manifests, rendering, CLI, runtime, and smoke behavior.
- `scripts/dev.sh`: canonical local checks.
- `~/runs/agentmux/`: local runtime state and logs written at runtime; not source.

When making changes, read the smallest relevant surface first instead of exploring broadly.

## Anti-Patterns
Do not do these unless I explicitly ask:
- introduce abstraction just because it looks cleaner
- over-model configuration that could stay simple
- force strict schemas where a simpler shape works
- optimize examples like test fixtures instead of documentation
- silently change the agreed architecture during implementation

## Implementation Check
Before changing config or command-building behavior, verify these questions explicitly:
- Does this change make mux composition clearer for a human?
- Does this change compile the mux into a real `vllm serve` command?
- Am I accidentally flattening a mux concept back into raw CLI details?
- If I am introducing a manifest field, does it affect launch behavior or is it dead metadata?

If the answer to the last question is dead metadata, stop and surface that problem clearly.

## Validation
Use validation to support the workflow.

Good validation:
- catches obvious mistakes
- catches missing required fields
- catches type issues where they matter
- smoke tests real boundaries

Bad validation:
- blocks easy experimentation
- takes ownership of fast-moving upstream surfaces
- requires code changes for routine exploration

## Decision Capture
When a decision matters, help capture it in:
- docs
- specs
- decisions
- AGENTS.md

Do not leave important decisions implicit.
