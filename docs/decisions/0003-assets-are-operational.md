# 0003: Assets Are Operational Stack Inputs

## Status
Accepted

## Context
The repo includes asset-oriented stack fields such as chat templates, tokenizer-related files,
prompt assets, and other files that make a backend behave like an agent stack rather than a raw
served model. If those fields remain passive metadata, the manifest lies about what the stack does.

## Decision
Treat asset-backed mux fields as operational stack inputs.

If an asset corresponds to a real `vllm serve` flag or launch-time behavior, the repo should
compile that asset into the final command or launch behavior.

Examples include:
- chat templates
- tokenizer-related assets
- LoRA-related files where modeled as stack composition

If a manifest field exists to describe a real stack part but does not affect launch behavior, that
is a bug or missing implementation, not acceptable steady-state behavior.

## Consequences
- Asset-backed fields must not be left as passive metadata when they clearly belong to launch behavior.
- The repo should prefer human stack concepts like `assets.chat_template` over pushing those values
  back into raw `args`.
- Tests and specs should lock down which assets compile into which launch flags.
