# Spec: benchmarking phase 1 case set

## Problem

`docs/specs/009-benchmarking.md` and `docs/specs/010-benchmarking-implementation-plan.md` define the benchmark design and phased rollout, but Phase 1 still needs an exact built-in case set.

Without a fixed case set, implementation will drift and model-to-model comparisons will be less meaningful.

This spec locks the first useful built-in case set for the `ghosty-local-agent` benchmark profile.

## Scope

This spec defines only the Phase 1 benchmark content:
- serving prompt shapes
- the exact 12 no-tools quality cases
- which cases may use the judge model
- what each case is trying to measure
- how each case should be scored at a high level
- what reliability signals Phase 1 should derive from these cases

This spec does not define:
- workspace-backed tool cases
- sandboxed bash cases
- long-context probes
- browser comparison UI

## Requirements

### 1. Phase 1 content summary

Phase 1 should include:
- 3 serving prompt shapes
- 12 no-tools quality cases
- 2 to 3 judge-scored cases
- reliability signals derived from those same cases

The case set should be small enough to run routinely, but broad enough to expose:
- structured output weakness
- instruction-following weakness
- hallucination / fabrication weakness
- concise practical helpfulness weakness

### 2. Serving prompt shapes

Phase 1 does not need a large serving corpus. It needs a small set that gives stable comparative signal.

Use 3 prompt shapes:

#### 2.1 Serving prompt A: short request

Purpose:
- approximate a common short harness turn
- useful for TTFT and short-response latency

Shape:
- a short user request
- low ambiguity
- brief expected answer

Example intent:
- ask for a one- or two-sentence terminal/coding answer

Recommended output cap:
- modest, such as 64 to 96 max tokens

#### 2.2 Serving prompt B: medium request

Purpose:
- approximate a more normal local-agent turn with a few constraints

Shape:
- moderate-length request
- one or two constraints
- medium expected answer

Example intent:
- explain a likely cause and suggest the next step concisely

Recommended output cap:
- modest, such as 128 to 192 max tokens

#### 2.3 Serving prompt C: longer request

Purpose:
- approximate a denser harness request without turning Phase 1 into a context benchmark

Shape:
- somewhat longer task framing
- a few details or constraints
- still a short practical answer target

Example intent:
- summarize a small task state and recommend a bounded next action

Recommended output cap:
- modest, such as 192 to 256 max tokens

### 3. Exact Phase 1 quality case set

Phase 1 should use exactly 12 no-tools quality cases.

## Group A — Structured output validity (3 cases)

These cases are deterministic-only and should be easy to audit.

### Case 1 — action_choice_enum

Purpose:
- test whether the model can choose one valid action from a small fixed set

Prompt shape:
- present a short situation and require exactly one choice from a closed enum such as:
  - `clarify`
  - `search`
  - `edit`
  - `answer`

Expected behavior:
- returns exactly one valid label
- chooses the correct one for the scenario

Scoring:
- exact match
- any extra text counts as failure

Reliability value:
- catches enum/control-surface weakness immediately

### Case 2 — exact_json_small_object

Purpose:
- test whether the model can return a small valid JSON object with exact keys only

Prompt shape:
- require JSON with a very small schema such as:
  - `{"task_type": ..., "needs_clarification": ..., "reason": ...}`

Expected behavior:
- valid JSON
- exact keys only
- values of expected type
- content matches scenario

Scoring:
- parse + schema + content checks

Reliability value:
- high-value signal for machine-usable output discipline

### Case 3 — bounded_structured_summary

Purpose:
- test whether the model can fill a constrained structured response without drifting

Prompt shape:
- require a small object or list with explicit field/value constraints
- example: exactly 3 short bullets or a JSON array of exactly 2 next steps

Expected behavior:
- correct structure
- exact count
- concise content

Scoring:
- deterministic structure/count checks plus simple content checks

Reliability value:
- catches models that technically respond but cannot stay bounded

## Group B — Instruction-following / concise response (3 cases)

These cases test discipline in practical harness-style responses.

### Case 4 — exactly_three_bullets

Purpose:
- test exact instruction following under simple formatting pressure

Prompt shape:
- ask for exactly 3 bullets and nothing else

Expected behavior:
- exactly 3 bullets
- no intro/outro paragraph
- bullets relevant to the task

Scoring:
- exact bullet count
- no forbidden extra prose
- relevance rubric

Reliability value:
- strong constraint-discipline signal

### Case 5 — hard_length_limit

Purpose:
- test whether the model can stay concise under a strict length bound

Prompt shape:
- answer under a specific character or sentence limit

Expected behavior:
- stays within bound
- still answers the request meaningfully

Scoring:
- deterministic length check
- simple relevance rubric

Reliability value:
- catches rambling models that are annoying in harness use

### Case 6 — constrained_task_plan

Purpose:
- test whether the model can produce a short practical plan without overexplaining

Prompt shape:
- ask for a tiny task plan with explicit constraints such as:
  - max 3 steps
  - one sentence per step
  - no assumptions beyond given facts

Expected behavior:
- follows all format constraints
- plan is sensible and bounded

Scoring:
- deterministic format checks
- rubric for practicality and assumption control

Reliability value:
- useful proxy for normal assistant discipline

## Group C — Clarification / anti-hallucination (3 cases)

These are among the most important trust cases for your use case.

### Case 7 — missing_path_requires_clarification

Purpose:
- test whether the model asks for missing file/path info instead of inventing it

Prompt shape:
- ask for a file-specific action without giving a file path or filename

Expected behavior:
- asks for clarification
- identifies the missing info
- does not invent a path
- does not claim completion

Scoring:
- rubric-based deterministic checks

Reliability value:
- core hallucination/trust signal

### Case 8 — ambiguous_destructive_request

Purpose:
- test whether the model notices ambiguity in a potentially destructive request

Prompt shape:
- ask for something that would be risky if executed without clarification
- example intent: removing or replacing something unspecified

Expected behavior:
- highlights ambiguity or risk
- asks for clarification or suggests a safer next step
- does not pretend the task is complete

Scoring:
- rubric-based deterministic checks

Reliability value:
- important early safety signal even before tool execution exists

### Case 9 — insufficient_evidence_no_fabrication

Purpose:
- test whether the model avoids inventing a diagnosis or conclusion when evidence is incomplete

Prompt shape:
- give a short incomplete technical situation and ask for a conclusion that cannot be known yet

Expected behavior:
- states uncertainty clearly
- gives a bounded next step or asks a clarifying question
- does not fabricate missing evidence

Scoring:
- rubric-based deterministic checks

Reliability value:
- catches confident nonsense that could otherwise score well on style

## Group D — Short practical helpfulness (3 cases)

These cases test whether the model is actually useful in a harness-style setting.

### Case 10 — short_bug_triage

Purpose:
- test concise practical coding diagnosis quality

Prompt shape:
- present a short error/symptom and ask for the most likely cause plus the next step

Expected behavior:
- identifies a plausible likely cause
- suggests a concrete next step
- stays concise
- does not overclaim certainty

Scoring:
- rubric-based
- judge-model eligible

Why judge helps:
- quality matters more than exact wording here

### Case 11 — short_edit_strategy

Purpose:
- test concise usefulness for an edit/change request without doing the edit yet

Prompt shape:
- describe a small code/config change request and ask what should be changed

Expected behavior:
- identifies the key change correctly
- mentions the right place or type of place to change
- keeps answer bounded
- avoids fake specifics if missing

Scoring:
- rubric-based
- judge-model eligible

Why judge helps:
- strong fit with practical harness usefulness

### Case 12 — short_terminal_next_step

Purpose:
- test whether the model gives a useful next action in a terminal-task scenario

Prompt shape:
- provide a small operational/coding situation and ask for the next best step

Expected behavior:
- gives a sensible next step
- respects constraints
- remains concise
- does not overcomplicate

Scoring:
- rubric-based
- judge-model eligible

Why judge helps:
- captures practical usefulness better than exact-match alone

### 4. Judge-model usage

Phase 1 should use judge-model scoring on only a small subset of cases.

Recommended judge-eligible cases:
- Case 10 — `short_bug_triage`
- Case 11 — `short_edit_strategy`
- Case 12 — `short_terminal_next_step`

Recommended Phase 1 default:
- use judge scoring on **2 of the 3** by default
- keep the third one rubric-only initially if implementation simplicity is better that way

Judge use should remain bounded and supplementary.

### 5. Reliability signals derived from the 12 cases

Phase 1 should derive these reliability signals directly from case outcomes:

#### 5.1 Structured output failure rate

Derived primarily from:
- Case 1
- Case 2
- Case 3

#### 5.2 Constraint violation rate

Derived primarily from:
- Case 3
- Case 4
- Case 5
- Case 6

#### 5.3 Hallucination / fabrication rate

Derived primarily from:
- Case 7
- Case 8
- Case 9
- optionally from helpfulness cases when they clearly invent unsupported specifics

#### 5.4 Empty / evasive / degenerate output rate

Derived from all 12 cases as applicable

#### 5.5 Judge disagreement note

Derived from:
- Cases 10–12 when judge scoring is enabled

### 6. Why this case set fits your use case

This Phase 1 set is intentionally not broad in an academic sense.
It is optimized for your actual decision loop:
- compare a full model to its quant
- compare that pair against other models and their quants
- see where each candidate is strong or weak
- avoid being fooled by fast but sloppy output

This set is good for that because:
- structured cases catch control/format weakness
- instruction cases catch harness-discipline weakness
- clarification cases catch dangerous hallucination behavior
- helpfulness cases give a small human-like usefulness check
- serving prompts cover latency/throughput basics
- VRAM is covered elsewhere in Phase 1 benchmark reporting for resource comparison

### 7. Should you raise or lower this case set?

My recommendation for your use case:
- keep this exact 12-case set initially

Raise only if, after real use, you find:
- multiple candidates tie too closely to separate them
- a repeated failure mode is missing
- the verdict feels too noisy

If you raise, add 3 more cases, not 10 more.

Lower only if you need a later explicit fast mode.
Even then, treat this 12-case set as the default reference profile.

### 8. Implementation notes

Recommended implementation pattern:
- case definitions live in code as built-in data structures first
- each case has:
  - `id`
  - `category`
  - `prompt`
  - `expected checks`
  - `judge_eligible`
  - `scoring metadata`

This keeps Phase 1 simple.

A later phase can move benchmark cases to a more data-driven format if needed, but that should not block the first implementation.

## Constraints

- Keep Phase 1 small and runnable.
- Do not add multi-turn/session cases here; long-context and sustained-session behavior belong to the future adjacent probe.
- Keep judge usage small.
- Keep deterministic checks primary.
- Do not block implementation on perfect wording of every prompt; what matters is stable intent and stable scoring.

## Acceptance Criteria

This case-set spec is successful if:
1. Phase 1 has an exact locked built-in case set.
2. The case set is small enough to run routinely.
3. The case set is broad enough to separate useful harness candidates from sloppy ones.
4. The case set supports full-vs-quant and model-vs-model comparison.
5. The case set leaves multi-turn, sandbox, and long-context work for later phases without muddying Phase 1.

## Open Questions

1. What exact final prompt wording should be used for each of the 12 cases?
2. Which 2 of the 3 helpfulness cases should use judge scoring by default in the first implementation?
3. Should the serving prompts be fully static strings in code, or small generated templates with frozen content?
