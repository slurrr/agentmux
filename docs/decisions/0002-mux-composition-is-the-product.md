# 0002: Mux Composition Is The Product

## Status
Accepted

## Context
The repo has repeatedly drifted toward treating raw backend flags as the only real surface and
mux-oriented stack fields as optional convenience. That drift creates the wrong tool: a thin app
around `vllm` flags instead of a cockpit for composing agent-serving stacks.

## Decision
Treat mux composition as the primary product of the repo.

A mux is a human-oriented agent-serving stack that compiles into a real `vllm serve` command.
The manifest structure exists to help a human compose that stack in meaningful parts rather than
flattening everything into raw CLI details.

The repo must therefore optimize for:
- human-readable mux composition
- inspectable rendered commands
- clean separation between raw backend/runtime flags and stack parts
- launch behavior that faithfully reflects the manifest

## Consequences
- Agents working in this repo must not reframe mux composition as secondary convenience.
- The success condition is not “all flags are representable.” The success condition is “the mux is
  easy to compose and launch as a real `vllm serve` command.”
- Changes that flatten mux concepts back into a raw CLI-shaped config require explicit justification.
