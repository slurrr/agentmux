# Spec supplement: judge audit JSON + suspicion-driven bench-show

## Status
Draft (captures judge shape + bench-show behavior agreed in chat).

## Goal
Keep `bench-show` extremely compact and readable by default, while still surfacing:
- deterministic failures (real constraints/outcomes)
- suspicious passes identified by an optional judge audit

The judge does **not** score and does **not** override deterministic pass/fail. It is an *auditor*.

## Judge audit (opt-in)

### Trigger
- `agentmux bench --judge`
  - runs a single judge request at the end of the run
  - stores the judge JSON in the result file

### Scope
Send **all non-workspace cases** to the judge.
Exclude workspace/tool cases:
- `group == "quality_with_tools"` or `kind == "workspace"`

### Input per case
For each included case, provide:
- `case_id`
- `group`
- `prompt`
- `response`
- `passed` (deterministic)
- `deterministic_failures`

### Judge instruction
Use this exact instruction (or semantically equivalent):

> “For each case, restate user intent in 1 line, then say if response actually fulfills it.
> Flag if ‘technically correct but unhelpful’. Quote the response fragment causing failure.
> No scoring.”

### Judge output contract (JSON)
The judge must return JSON only: an array of objects with the following keys:

- `case_id` (string; must match input)
- `intent` (string; 1 line)
- `fulfills_intent` (boolean)
- `technically_correct_but_unhelpful` (boolean)
- `flag` (boolean)
- `quote` (string; response fragment)
- `note` (string; short, optional)

Rules:
- The judge should set `flag=true` when either:
  - `fulfills_intent=false`, OR
  - `technically_correct_but_unhelpful=true`
- The judge should keep fields short. (Exact char limits not locked; implementation should apply truncation when rendering.)

### Storage
In the result JSON, store:
- top-level judge metadata already present (`result["judge"]`)
- and additionally:
  - `result["audit"]["judge_review"] = <judge_output_array>`
  - `result["audit"]["judge_prompt_version"] = "audit-v1"` (or similar)

## bench-show: suspicion-driven view

### Default view
`agentmux bench-show <result>` prints:
- header
- perf summary
- deterministic bench scorecard

Then, under **cases**, it prints full details only for:
1) deterministic failures/errors (`passed=false` or `status=failed`)
2) judge-flagged cases (`audit.judge_review[*].flag == true`)

All other passing cases are not expanded.

### Flags
- `bench-show --judge`
  - prints the judge review JSON (pretty-printed) and exits
- `bench-show --all`
  - expands all cases
- `bench-show --failures-only`
  - expands only deterministic failures/errors (ignores judge)
- `bench-show --case <id>`
  - expands exactly one case (and includes judge entry if available)

### Rendering judge info in expanded cases
When a case is expanded and there is a judge entry for it, include:
- `intent`
- `fulfills_intent`
- `technically_correct_but_unhelpful`
- `quote`
- `note` (if present)

## Non-goals
- Using judge output to change pass/fail.
- Sending workspace/tool cases to judge.
- Reintroducing semantic rubric scoring into deterministic scoring.
