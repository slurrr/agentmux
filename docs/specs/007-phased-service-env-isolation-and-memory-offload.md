# Spec: phased service env isolation and memory offload

## Problem

`agentmux` currently works well as a single cockpit for launching a multi-service agent stack, but the local runtime shape still couples multiple heavy Python/native dependency surfaces into one repo environment.

Current observed concerns:
- `vllm` and Hindsight are launched from the same repo-managed environment.
- Hindsight local ML work brings in its own native stack surface (for example ONNX Runtime, NumPy/SciPy/OpenBLAS, uvloop, sentence-transformers-related dependencies).
- A recent long-uptime core dump occurred in `hindsight-api`, not in `vllm`, which suggests memory-service stability should be improved independently from the LLM service.
- Future `vllm` upgrades, especially the planned move to `0.20.x`, are expected to shift the preferred CUDA / PyTorch / Python alignment. That should not force the Hindsight service to move in lockstep if it does not need the same environment.

The goal is to keep the current repo and cockpit workflow intact while reducing cross-service dependency coupling and creating a cleaner path toward stronger memory-service isolation.

## Scope

This spec covers a phased implementation plan for:
- splitting service runtimes into isolated environments while keeping one repo and one `agentmux` control plane
- pairing the first service-env split with the future `vllm 0.20.x` upgrade
- evaluating and then optionally adopting TEI-backed embeddings and possibly reranking for Hindsight
- evaluating and then optionally adopting a dedicated CPU host for memory-related CPU services

This spec does not require immediate implementation. It is a rollout plan with explicit verification points between phases.

## Requirements

### Workflow requirements
- Keep `agentmux` as the single cockpit for composing and launching the stack.
- Preserve the current mental model of one mux containing multiple named services.
- Preserve a single `agentmux up <stack>` workflow even when services run in different environments or on different hosts.
- Preserve `render` as the source of truth for what will actually launch or be reused.

### Phase 1 requirements: service env isolation, starting with Hindsight
- Add a service-level runtime mechanism that allows a service to run from its own environment without requiring a separate repo.
- Start with a Hindsight-first split because Hindsight may need to move before `vllm` does.
- Create a new dedicated Hindsight environment and move the memory service there first.
- Keep the current shared env intact as the known-good fallback while the Hindsight split is being validated.
- After Hindsight is stable in its own env, create a separate `vllm` environment and pair that move with the future upgrade from `vllm 0.19.1` to `0.20.x`.
- Keep Hindsight in its own environment so the `vllm 0.20.x` stack can be aligned with what `vllm` recommends without dragging Hindsight through the same dependency transition.
- Keep current stack topology unchanged during this phase:
  - local `vllm`
  - local Hindsight
  - Hindsight local embeddings/reranking as currently configured
- Make the service-env split visible in the rendered launch plan.

### Phase 1 verification requirements
Before moving to the next phase, verify:
- `agentmux render` shows the correct executable/env boundary for the services that have been split so far.
- `agentmux up` can still launch both services from one stack.
- Hindsight starts cleanly in its isolated env.
- after the later `vllm` move, `vllm 0.20.x` starts cleanly in its isolated env.
- at least one real stack run validates the expected `pi-ghosty`-style workflow against the split-env stack.
- if a failure occurs, rollback should be possible by returning to the prior service env definitions without redesigning the whole stack model.

### Phase 2 requirements: TEI evaluation and staged memory offload
- Evaluate TEI as the preferred dedicated embeddings service for Hindsight.
- Start with embeddings first.
- Verify whether reranking can also move cleanly into TEI or an equivalent dedicated service boundary.
- Keep the Hindsight API/frontends contract stable while changing backend service topology.
- The mux should still represent the stack in human terms, whether TEI is launched locally, reused externally, or pointed at a remote host.
- If TEI is introduced, it should be treated as a real service boundary, not just undocumented background infra.

### Phase 2 verification requirements
Before moving to the next phase, verify:
- recall quality and latency are acceptable with TEI-backed embeddings.
- retain/reflect flows still behave as expected.
- reranker behavior is either:
  - proven acceptable in the TEI-based shape, or
  - explicitly kept local / deferred with the reason documented.
- the operational shape is still simple enough to manage from `agentmux`.
- the service split materially reduces the amount of native ML work owned directly by the Hindsight API process, if that is part of the chosen TEI integration shape.

### Phase 3 requirements: dedicated CPU host evaluation and adoption
- Evaluate whether memory-related CPU services should move to a dedicated CPU host.
- The evaluation should consider at least:
  - embeddings
  - reranking
  - Hindsight API itself
- The decision should be based on observed value, not assumption.
- If adopted, the remote-host shape must still fit the one-repo / one-mux / one-`up` operational model.
- The stack definition should make it clear which services are launched locally and which are reused remotely.

### Phase 3 verification requirements
Before calling the rollout complete, verify:
- long-running uptime is improved or at least operationally cleaner.
- CPU-heavy memory services no longer contend with the main workstation in ways that hurt the agent-serving workflow.
- the remote-service shape remains inspectable and understandable through `agentmux render`, `status`, and related runtime surfaces.

## Constraints

- Keep the repo simple; do not turn this into a generic orchestrator project.
- Do not require separate repos just to achieve runtime isolation.
- Avoid introducing dead metadata. If a service runtime field is added, it must affect real launch behavior.
- Prefer phased rollout with verification pauses over a single big migration.
- Preserve the current human-centered mux workflow.
- The current stack remains the known-good baseline until a phase is explicitly validated.

## Proposed rollout

### Phase 0: hold current baseline
- Keep the current stack as-is on `vllm 0.19.1`.
- Treat this as the comparison point for later phases.
- Do not force immediate Hindsight or TEI changes while the current stack is still being used.

### Phase 1a: split out Hindsight first
Intent:
- create a dedicated Hindsight env first
- move only the memory service to that env
- keep the current shared env untouched as fallback
- keep one stack and one launch surface

Expected outcome:
- immediate path for Hindsight-only upgrades
- reduced blast radius for memory-service dependency changes
- first proof that per-service envs fit the cockpit model

### Phase 1b: split out `vllm` and upgrade it later
Intent:
- create a dedicated `vllm` env after the Hindsight split is proven
- upgrade only the `vllm` service path to `0.20.x`
- retire the old shared env only after both service-specific envs are validated

Expected outcome:
- cleaner dependency boundaries
- easier `vllm` upgrades going forward
- reduced cross-service native dependency coupling

### Phase 2: evaluate TEI-backed memory CPU services
Intent:
- move embeddings out first
- verify reranker options second
- keep Hindsight as the memory API contract

Expected outcome:
- lighter Hindsight API process
- clearer service boundaries for CPU-heavy memory work
- better basis for long-running memory stability

### Phase 3: evaluate and, if justified, move memory CPU services to a dedicated host
Intent:
- reserve CPU resources for memory-related services
- reduce workstation contention
- keep the same mux-driven control model

Expected outcome:
- stronger operational isolation
- cleaner long-uptime shape for memory services
- optional separation of memory infra from the main interactive workstation

## Acceptance criteria

This spec is satisfied when:
- there is an implemented path to run different services in different environments while keeping one repo and one stack launcher
- `vllm` can be upgraded independently from Hindsight as part of the planned `0.20.x` move
- later phases can introduce TEI and optional remote CPU service placement without breaking the cockpit model
- each phase has an explicit verification step before the next phase begins
- important decisions and results from each phase are recorded in follow-up specs/decisions/docs as needed

## Open questions

- What is the smallest manifest/runtime field that can express per-service env selection without over-modeling?
- Should service env selection live in manifests, repo-local defaults, or both?
- How should `render` represent remote reuse versus local launch for TEI-like services?
- If reranking does not fit TEI cleanly, should it remain inside Hindsight’s env or become a separate dedicated service type?
- At Phase 3, which services actually belong on a dedicated CPU host:
  - embeddings only
  - embeddings + reranking
  - embeddings + reranking + Hindsight API
- What minimum uptime / latency / operational simplicity threshold is enough to justify the dedicated CPU host move?
