# Plan: implement benchmarking reframe (perf + deterministic scoring + manual sandbox session)

## Status
Draft plan based on `docs/specs/017-benchmarking-reframe-perf-deterministic-prompts-and-manual-sandbox-session.md`.

## Why
We want a bench we can **run, glance at, and trust** for comparing models and quant variants.
The current failure mode is semantic rubric drift (keyword/regex heuristics) creating false negatives.

This plan implements the reframe:
- keep prompts
- keep scores
- but **only score deterministic constraints/outcomes**
- put prompt text + pass/fail criteria in one reference doc (`bench-prompts.md`)
- add a Phase 3 manual sandbox session workflow (pi + bwrap + disposable repo worktree)

---

## Decisions / clarifications (locked)

### D1. Drills still produce a score
- For non-workspace prompts (structured_output / instruction_following / clarification / helpfulness drills):
  - keep `score` in outputs
  - interpret score as **constraint-clean score** (i.e. 1.0 if all deterministic constraints passed, else 0.0)
- The CLI should show:
  - run-level score summary
  - case-by-case pass/fail (right/wrong)

### D2. Prompt set reference doc
Add a human-readable reference doc:
- `docs/reference/bench-prompts.md`

It should list:
- case id
- group
- prompt text
- deterministic pass/fail criteria (only)

This is the canonical “what does the bench mean?” reference so the CLI can stay compact.

### D3. Workspace conversation incomplete handling
We keep “conversation incomplete” (e.g. `max_turns`, `request_error`) as a **case failure**.

However we will improve *diagnostics and fairness*:
- Even if the conversation ends at `max_turns`, we still snapshot the workspace and run the deterministic
  outcome checks.
- This ensures failures reflect **observable workspace incorrectness** (e.g. wrong edits) even when
  the stop reason is `max_turns`.

Rationale:
- If the model edited files incorrectly, the case should fail regardless of stop reason.
- If the model edited correctly but failed to produce a final answer, we still want:
  - outcome correctness recorded
  - but the case fails due to incomplete conversation.

This prevents “max_turns” from masking the real failure reason.

### D4. Phase 3 session shape
- Disposable worktree per session under `~/runs/agentmux/bench-sessions/<id>/worktree`
- Launch interactive **pi** inside a **bwrap** sandbox
- Network enabled
- All tools allowed (bash included)
- Always capture transcript + tool trace + git diff summary

---

## Implementation milestones

### M0 — Add prompt reference doc (`bench-prompts.md`)
**Goal:** make prompt set + deterministic criteria inspectable without reading code.

Deliverables:
- New file: `docs/reference/bench-prompts.md`
- Contents derived from:
  - `src/agentmux/bench_cases.py` (drills)
  - `src/agentmux/bench_workspace.py` (workspace cases)
  - deterministic criteria documented in code (post-M1)

Approach:
- Start as a hand-written doc (fast).
- Optional follow-up: generate/update it automatically from case definitions.

Files:
- add: `docs/reference/bench-prompts.md`

---

### M1 — Remove semantic rubric scoring from drills (keep deterministic constraints + score)
**Goal:** make drill scoring actually deterministic; no keyword/regex “quality” grading.

Key rule change:
- Drill cases pass/fail depends only on deterministic constraints (JSON validity, exact counts, max sentences/chars, etc.).
- Semantic rubric checks are removed or converted into non-scoring annotations.

Code changes:
- `src/agentmux/bench_score.py`
  - Update handlers that currently add `rubric_failures` for semantic adequacy.
  - Ensure `CaseEvaluation.passed` and `score` track deterministic constraints only.
  - Keep the `rubric_*` fields for backward compatibility but typically leave them empty for drills.

Tests:
- Add regression tests for formerly-brittle responses so we don’t reintroduce semantic grading.

Acceptance:
- Re-score the most recent run (e.g. `20260505-100612...json`) and verify:
  - drill failures are only constraint violations
  - “helpfulness/clarification” semantics no longer fail due to missing keywords

---

### M2 — Workspace scoring: keep outcome-based scoring; improve incomplete-conversation reporting
**Goal:** preserve workspace outcome determinism and improve failure attribution.

Code changes:
- `src/agentmux/bench_workspace.py`
  - When `stop_reason != final_answer`:
    - still compute workspace diffs and run `_evaluate_workspace_case`
    - include both:
      - `deterministic_failures` from stop_reason
      - `file_checks` / outcome failures (if any)
  - Reduce/disable any pass/fail dependence on “final answer mentioned X” style checks.

Tests:
- Add a unit test ensuring that on `max_turns`:
  - outcome checks are still evaluated and included in the result payload.

---

### M3 — bench-show v2 redesign (per spec 020)
**Goal:** clean, compact bench-show that matches the reframe.

Reference spec:
- `docs/specs/020-bench-show-v2-perf-defaults-and-bench-overrides.md`
- judge behavior: `docs/specs/019-judge-audit-json-and-bench-show-suspicion-driven-view.md`

Code changes:
- `src/agentmux/bench_report.py` / `bench-show` rendering:
  - Header (identity + key config + bench overrides)
  - Perf immediately under header (endpoint perf)
  - Deterministic bench scorecard
  - Expanded blocks only for:
    - failures (prompt/response + deterministic failures)
    - judge-flagged cases (prompt/response + judge reason/comment)
  - Default prompt/response truncation: 1200 chars each; `--full` disables truncation.
  - Remove/replace old "judge unavailable" warning.

Acceptance:
- `agentmux bench-show <run.json>` fits on one screen when everything passes.
- When there are failures/flags, only those are expanded.
- `--case <id>` and `--full` provide deep inspection without cluttering default output.

---

### M4 — Endpoint perf on by default (2-lane perf profile) + bench launch override
**Goal:** perf is first-class and always runs; server is launched in bench mode with required bench overrides.

Reference spec:
- `docs/specs/020-bench-show-v2-perf-defaults-and-bench-overrides.md`

Code changes:
- `src/agentmux/bench.py`
  - Run endpoint perf by default.
  - Ensure bench-mode launch overrides include: `--max-num-seqs 32`.
  - Capture perf lane metrics + artifacts in the run JSON.

- `src/agentmux/bench_perf_vllm.py`
  - Remove hidden env-var gating for default perf.
  - If a vLLM-native script wrapper is used, it should be invoked deterministically with a fixed profile.

Outputs:
- Store perf artifacts under `~/runs/agentmux/benchmarks/perf/` and reference them from the run JSON.

Acceptance:
- A bench run always shows perf metrics in `bench-show` without needing env vars.
- Perf uses standardized lanes and concurrencies.

---

### M5 — Phase 3 manual sandbox session command
**Goal:** one command sets up a disposable worktree + bwrap wrapper + launches pi + captures artifacts.

Code changes:
- new: `src/agentmux/bench_session.py`
- CLI integration: `src/agentmux/main.py`

Runtime layout:
- session root: `~/runs/agentmux/bench-sessions/<id>/`
  - `worktree/`
  - `transcript.*`
  - `tool_trace.*`
  - `git_diff.patch` (or `diff.txt`)
  - `summary.json`

Notes:
- We will avoid any destructive operations on user repos.
- Session worktree is disposable; cleanup can default to “preserve” with an explicit `--cleanup`.

---

## Minimal commands to validate each milestone

- Unit tests:
  ```bash
  pytest -q
  ```

- Re-score latest run after M1/M2:
  ```bash
  python - <<'PY'
  import json
  p='/home/poop/runs/agentmux/benchmarks/20260505-100612-qwen3_5-fp8d-bench-ghosty-local-agent.json'
  data=json.load(open(p))
  print('cases', len(data.get('cases') or []))
  # after implementation we’ll add a real rescore command; this is just a placeholder sanity check.
  PY
  ```

---

## Open items (intentionally deferred)
- Auto-generation of `bench-prompts.md` from code.
- Any composite “overall score” across perf + tools + drills. The plan focuses on separate sections.
- Phase 3 repo selection/bootstrapping (user will create/choose the repo; we only consume it).
