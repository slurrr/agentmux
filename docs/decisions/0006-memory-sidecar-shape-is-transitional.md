# 0006: Keep `[stack.memory]` as a transitional shape; refactor to service-shaped memory later

## Status
Accepted

## Context
`agentmux` was built around launching separate services with service-level configuration.

For Hindsight v1, memory was added as a stack-sidecar section (`[stack.memory]`) to get working local behavior quickly:
- launch Hindsight only when configured
- derive memory LLM backend from the primary vLLM service
- keep frontend bank/base-url configuration client-side

This works, but it is not the final shape we want.

## Decision
We will **keep `[stack.memory]` as-is for now** and not expand it further.

We acknowledge that memory likely should have been modeled as a service-shaped entry from the start.
That refactor is deferred intentionally.

Until that refactor:
- treat `[stack.memory]` as a transitional compatibility surface
- avoid adding broad new config surface to `[stack.memory]`
- use targeted operational env settings when needed (for example CPU-forcing Hindsight embedding/reranker)

## Consequences
Positive:
- preserves current working behavior with minimal churn
- avoids another redesign during active stabilization

Tradeoffs:
- memory config is not fully aligned with the repo’s long-term service-first shape
- per-process control for memory is less explicit than a true service model

## Follow-up
Planned future work is a refactor that removes special-case memory shape and models Hindsight as a normal service with explicit per-service config.
