# Spec: benchmarking implementation plan

## Problem

`docs/specs/009-benchmarking.md` locks the benchmark design, but implementation should be phased so `agentmux` gets a useful benchmark tool quickly without waiting for workspace simulation, sandboxed bash, or long-context probing.

This plan turns the benchmark design into an implementation sequence that:
- delivers a small useful benchmark first
- keeps result-file and command-shape compatibility across phases
- avoids overbuilding the first pass
- leaves a clean path to richer tool and sandbox evaluation later

## Scope

This plan covers:
- phase ordering
- recommended minimal case counts
- recommended reliability checks
- result-file shape decisions needed early
- implementation surfaces in this repo
- validation strategy

This plan does not redefine the benchmark design. It applies `docs/specs/009-benchmarking.md`.

## Requirements

### 1. Phase 1 goal: immediate practical usefulness

Phase 1 should answer the core question:

> Is this stack good enough for local harness use, and how does it compare to another stack or quant?

Phase 1 should optimize for:
- speed of implementation
- speed of execution
- repeatability
- category-level usefulness
- minimal prompt/case count that still gives confidence

Phase 1 should **not** try to be exhaustive.

### 2. Recommended Phase 1 benchmark shape

Phase 1 should include exactly four major parts:
- serving
- VRAM / memory footprint
- quality without tools
- reliability / anti-garbage

Tool-using workspace simulation should be deferred to Phase 2.

### 3. Recommended Phase 1 case counts

The goal is not statistical rigor in the abstract. The goal is enough coverage that obvious regressions and meaningful tradeoffs become visible when comparing:
- full vs quantized versions of the same model
- one model family vs another

Recommended Phase 1 size:

#### 3.1 Serving cases

Use a small fixed prompt set with controlled lengths.

Recommended serving set:
- 3 prompt shapes
  - short prompt
  - medium prompt
  - longer prompt
- each shape run at concurrency:
  - `1`
  - `2`
  - `4`

This is enough for a first pass because you mainly want:
- TTFT feel
- decode throughput
- whether concurrency degrades badly

You do **not** need a large prompt corpus for serving metrics in Phase 1.

#### 3.2 VRAM / memory-footprint capture

Phase 1 should capture basic observed GPU memory stats for the running stack when available.

Recommended metrics:
- used VRAM after model load
- free VRAM remaining
- total VRAM
- percentage consumed

Reasoning:
- one of your main comparison questions is quant savings versus full weights
- basic VRAM stats are cheap and high-value
- they belong beside serving metrics, not hidden in notes

#### 3.3 No-tools quality cases

Recommended count:
- **12 total cases**

Reasoning:
- fewer than ~8 is too easy to overfit mentally and may miss a major weakness
- more than ~15 starts to slow iteration and create unnecessary eval design work
- 12 is enough to give a useful category breakdown without becoming a project of its own

Recommended mix:
- 3 structured-output validity cases
- 3 instruction-following / concise-response cases
- 3 clarification / anti-hallucination cases
- 3 short practical helpfulness cases

This is the best default for your use case because it centers:
- local coding/terminal assistant behavior
- structured output reliability
- hallucination avoidance
- concise practical usefulness

#### 3.4 Judge-scored cases

Recommended count:
- **2 to 3 of the 12 quality cases**

Reasoning:
- enough to add human-like sanity checking
- cheap to run
- limited judge influence
- keeps deterministic scoring primary

Recommended use:
- short practical helpfulness cases only
- not JSON-validity or exact-match cases
- not all open-ended cases

#### 3.5 Reliability checks

Recommended count:
- no separate prompt corpus required
- derive reliability signals from the 12 quality cases plus serving responses where relevant

This keeps Phase 1 small.

### 4. Recommended Phase 1 quality case types

Phase 1 should use a small built-in case set under the `ghosty-local-agent` profile.

Recommended case families:

#### 4.1 Structured-output validity (3 cases)

Purpose:
- catch models that cannot reliably produce bounded machine-usable output

Case style:
- return JSON with exact required keys
- choose one action from a small enum
- fill a small structured object with concise values

Scoring:
- deterministic only

Why this matters for your use case:
- if a model cannot do this, it will be painful in an agent harness even if it sounds smart

#### 4.2 Instruction-following / concise response (3 cases)

Purpose:
- measure whether the model follows tight practical instructions

Case style:
- answer in exactly N bullets
- answer under a character or sentence limit
- produce a short shell/task plan without rambling

Scoring:
- deterministic + rubric

Why this matters:
- local harness use heavily rewards disciplined, bounded output

#### 4.3 Clarification / anti-hallucination (3 cases)

Purpose:
- measure whether the model avoids inventing details

Case style:
- missing path / missing filename
- insufficient information to safely complete a request
- ambiguous instruction that should trigger clarification

Scoring:
- rubric-driven deterministic checks:
  - asked for clarification
  - identified missing info
  - did not invent missing details
  - did not claim completion

Why this matters:
- this is one of the most important trust signals for local agent use

#### 4.4 Short practical helpfulness (3 cases)

Purpose:
- measure whether the model gives useful concise task-oriented answers

Case style:
- short coding diagnosis
- short edit plan
- short terminal-task next-step suggestion

Scoring:
- rubric-based
- 2 to 3 of these may use the judge model

Why this matters:
- this is where "feels useful in the harness" shows up without requiring full tool simulation yet

### 5. Recommended Phase 1 VRAM reporting

Phase 1 should report a small VRAM summary derived from observed runtime state.

Recommended display and result-file fields:
- used VRAM
- free VRAM
- total VRAM
- percent used

Recommended collection strategy:
- query local GPU state from the benchmark host while the target stack is already loaded
- if multiple GPUs are visible, prefer the GPU(s) associated with the served process when that can be determined simply; otherwise report the observed device scope clearly
- if stats cannot be collected reliably, record them as unavailable rather than guessing

Why this is enough for Phase 1:
- you mainly want practical comparison of full versus quantized stack footprint
- you do not need deep allocator or fragmentation analysis in the first pass

### 6. Recommended Phase 1 reliability signals

You asked where reliability checks should begin. For your use case, start with checks that catch the most annoying and dangerous local-agent failures.

Recommended Phase 1 reliability checks:

#### 5.1 Structured output failure rate

Definition:
- fraction of structured-output cases that fail parsing or schema checks

Why:
- high-value early signal
- highly repeatable
- strongly predictive of harness friction

#### 5.2 Constraint violation rate

Definition:
- fraction of cases where the model violates explicit task constraints
- examples:
  - too verbose
  - wrong number of bullets
  - wrong output format
  - forbidden extra explanation

Why:
- discipline matters a lot in harness use

#### 5.3 Hallucination / fabrication rate

Definition:
- fraction of cases where the model invents missing facts, file paths, success claims, or unsupported conclusions

Why:
- critical for deciding whether a model is safe enough to trust in an agent loop

How to score in Phase 1:
- detect from clarification and structured cases first
- no need for a separate hallucination benchmark suite

#### 5.4 Empty / evasive / degenerate output rate

Definition:
- fraction of cases where output is empty, uselessly generic, self-contradictory, or obviously non-responsive

Why:
- catches weak local models that technically respond but are not actually usable

#### 5.5 Judge disagreement note

Definition:
- when judge-scored cases are used, record whether deterministic/rubric expectations and judge assessments diverge meaningfully

Why:
- useful for auditing without making the judge dominant

This should be a note/signal, not a top-level failure metric in Phase 1.

### 7. Recommended Phase 1 verdict thresholds

The verdict should stay simple.

Suggested first-pass rule shape:
- `recommended`
- `usable_with_tradeoffs`
- `not_recommended`

Recommended initial logic:

#### 6.1 Hard blockers for `recommended`

Any one of these should prevent `recommended`:
- structured output failure rate > 10%
- hallucination / fabrication rate > 10%
- constraint violation rate > 20%
- empty / evasive / degenerate output rate > 10%

#### 6.2 Hard blockers for `usable_with_tradeoffs`

Any one of these should force `not_recommended`:
- structured output failure rate > 25%
- hallucination / fabrication rate > 20%
- constraint violation rate > 35%
- empty / evasive / degenerate output rate > 20%

These are intentionally simple starting thresholds.

Why these numbers are reasonable for your use case:
- you are comparing local harness candidates, not publishing scientific evals
- you want quick practical signal
- repeated bad behavior above these rates will be very noticeable in real use

### 8. Should you raise or lower the Phase 1 size?

For your use case, my recommendation is:

#### Keep Phase 1 at the suggested default if:
- you want something you will actually run often
- you compare many models/quants
- you care about turnaround time
- you want enough signal without benchmark fatigue

#### Raise case count slightly if:
- you only benchmark occasionally
- you care more about confidence than run speed
- your candidate models are often very close and hard to separate

If raising, I would go only to:
- 15 or 18 no-tools quality cases

I would **not** jump beyond that initially.

#### Lower case count only if:
- you need ultra-fast iteration during active quant tuning

If lowering, I would not go below:
- 9 no-tools quality cases

Below that, verdicts get too fragile.

### 9. Phase sequence

## Phase 1 — minimal benchmark

Goal:
- deliver immediate value with small implementation scope

Includes:
- CLI command: `agentmux bench <stack>`
- already-running stack only
- built-in `ghosty-local-agent` profile
- serving metrics for concurrency `1`, `2`, `4`
- basic VRAM / memory-footprint reporting
- 12 no-tools quality cases
- 2 to 3 judge-scored cases using `gpt-5.4-mini` when available
- reliability signals derived from those cases
- compact terminal summary
- one JSON result file

Defers:
- workspace cases
- tool simulation
- sandboxing
- compare command
- long-context probe

## Phase 2 — workspace-backed tool evaluation

Goal:
- start measuring actual agent-like file/task behavior safely

Includes:
- ephemeral workspace fixture copies
- structured tool traces
- small safe tool set:
  - `read`
  - `write`
  - `edit`
  - optionally `find` / `ls`
- deterministic scoring based on:
  - file diffs
  - expected edits
  - final answers
  - tool-choice validity

Defers:
- bash-enabled sandbox cases

## Phase 3 — sandboxed repo/playground simulation

Goal:
- test more realistic repo-style behavior, including bash

Includes:
- sandbox abstraction
- `bwrap` backend
- bash-enabled cases
- workspace preservation option
- repo/playground fixtures
- safety-aware command scoring

## Phase 4 — result comparison UX

Goal:
- improve inspection of benchmark files

Possible additions:
- compare subcommand
- richer summary tables
- category diffs
- browser/file-selection UI later

## Phase 5 — long-context probe

Goal:
- measure sustained-context and heavy-prompt behavior separately from benchmark score

Possible additions:
- separate command or explicit mode
- large-context retention checks
- long-session consistency checks
- optional post-context task quality

### 10. Early implementation file plan

Recommended initial repo surfaces:
- `src/agentmux/main.py`
  - add `bench` subcommand
- `src/agentmux/bench.py`
  - top-level benchmark orchestration
- `src/agentmux/bench_cases.py`
  - built-in Phase 1 case definitions
- `src/agentmux/bench_score.py`
  - scoring and verdict logic
- `src/agentmux/bench_report.py`
  - summary rendering + JSON result payload assembly
- `src/agentmux/bench_judge.py`
  - optional judge-model integration via `/home/poop/.pi/agent/auth.json`
- `tests/test_bench.py`
  - basic benchmark orchestration tests
- `tests/test_bench_score.py`
  - score/verdict logic tests
- `tests/test_bench_report.py`
  - result shape tests

Later phases can add:
- `src/agentmux/bench_workspace.py`
- `src/agentmux/bench_tools.py`
- `src/agentmux/bench_sandbox.py`
- `bench/fixtures/...`

### 11. Phase 1 JSON result shape

Phase 1 should establish the durable shape so later phases can extend it without breaking comparisons.

Recommended top-level shape:

```json
{
  "benchmark_version": "0.1",
  "profile": "ghosty-local-agent",
  "stack": {
    "name": "qwen3_5_9b",
    "path": "mux/lab/qwen3_5_9b.toml"
  },
  "run": {
    "started_at": "...",
    "finished_at": "...",
    "target_mode": "already_running"
  },
  "environment": {
    "python": ".venv-vllm/bin/python"
  },
  "judge": {
    "enabled": true,
    "provider": "openai",
    "model": "gpt-5.4-mini",
    "auth_source": "/home/poop/.pi/agent/auth.json"
  },
  "summary": {
    "overall_score": 0.78,
    "verdict": "usable_with_tradeoffs",
    "blocking_weaknesses": [],
    "categories": {
      "serving": {...},
      "vram": {...},
      "quality_no_tools": {...},
      "reliability": {...}
    }
  },
  "cases": [...]
}
```

Important:
- later phases can add `quality_with_tools`, `workspace`, and `sandbox` details without changing the basic file identity
- Phase 1 should already reserve a stable place for VRAM / memory-footprint reporting because that is part of the baseline comparison value

### 12. Validation strategy

Recommended validation for Phase 1:
- unit-test score logic heavily
- unit-test result JSON shape
- unit-test deterministic check helpers
- smoke-test CLI with mocked HTTP responses
- do not require real model inference in normal unit tests

Recommended manual validation once Phase 1 exists:
- run against one known-good stack
- run against one clearly weaker/smaller stack
- run against one quant of the known-good stack
- verify the category breakdown matches operator intuition

### 13. Guidance for your use case

Given your goals, I recommend you **do not increase complexity yet**.

Best defaults for you:
- 12 no-tools quality cases
- 2 to 3 judge-scored cases
- serving prompts kept very small in count
- basic VRAM / memory-footprint reporting included from the start
- reliability derived from those cases, not separate eval suites

I would only raise scope early if you find after real runs that:
- many models tie too closely to separate them
- the verdict feels noisy
- you repeatedly encounter a failure mode the cases do not capture

Until then, smaller is better because you are much more likely to actually use it regularly.

## Constraints

- Follow `docs/specs/009-benchmarking.md`.
- Prefer the smallest useful Phase 1.
- Keep deterministic and rubric scoring primary.
- Keep judge usage limited and cheap.
- Do not block Phase 1 on workspace, sandbox, or long-context work.
- Preserve forward compatibility for later phases.

## Acceptance Criteria

This plan is successful if:
1. It gives a clear Phase 1 scope that is useful immediately.
2. It prevents overbuilding the first implementation.
3. It gives reasonable default case counts, VRAM reporting, and thresholds for your local harness use case.
4. It leaves a clear path to workspace, sandbox, and long-context phases later.
5. It keeps the benchmark something you will realistically run often.

## Open Questions

1. Which exact 12 Phase 1 cases should be used in the first built-in `ghosty-local-agent` profile?
2. What exact serving prompts should represent short, medium, and long request shapes?
3. Should Phase 1 include one tiny multi-turn no-tools case, or stay strictly single-turn?
