# Spec: benchmarking phase 2 workspace cases

## Problem

Phase 1 gives useful serving and no-tools quality signal, but it still leans on benchmark-shaped prompts.

Phase 2 needs to answer a more practical question:

> Can this served stack act like a small local harness agent in realistic file/task work?

This phase should stay comparison-friendly across models and quants, but move closer to real agent behavior.

## Scope

This spec locks the first small useful Phase 2 workspace-backed case set and how it is scored.

It defines:
- the initial workspace case count
- fixture style
- tool subset
- case prompts
- deterministic scoring targets
- how tool traces affect scoring
- how Phase 2 extends the existing result shape and CLI output

It does not define:
- bash-enabled sandbox cases
- repo-wide shell workflows
- long-context probes
- judge-heavy scoring

## Design rules

- Reuse the Phase 1 benchmark architecture and result-file shape.
- Extend the benchmark; do not redesign it.
- Keep prompts realistic and harness-like.
- Prefer deterministic scoring from observed workspace outcomes.
- Use vLLM-exposed metrics where available; do not invent extra runtime heuristics unless needed.
- Keep the case count small enough for routine reruns.
- Do not add bash until a real sandbox boundary exists.

## Phase 2 case set

Use 4 workspace-backed cases.

This is the smallest useful set that covers:
- single-file edit success
- multi-file propagation
- inspect-then-write behavior
- ambiguity handling without hallucinated completion

### Case 1 — update_api_base_url

Purpose:
- realistic single-file config edit
- tests read -> edit -> brief completion summary

Fixture:
- `config/app.toml`

Prompt shape:
- explicit file path
- explicit target value
- asks for a brief summary after editing

Deterministic outcome:
- `config/app.toml` has the expected new URL
- no unrelated files changed

Trace expectations:
- should read before editing
- should not issue invalid tool calls

Final answer expectations:
- briefly states the file changed
- does not invent extra work

### Case 2 — rename_timeout_key_everywhere_needed

Purpose:
- realistic cross-file consistency update
- tests whether the model can inspect and propagate a rename cleanly

Fixture:
- `config/app.toml`
- `docs/config.md`

Prompt shape:
- rename a config key while preserving value/meaning
- asks for a short touched-files summary

Deterministic outcome:
- config and docs both use `request_timeout_secs`
- old key name is gone from those target files
- no unrelated files changed

Trace expectations:
- should inspect both files before editing
- should avoid invalid arguments

Final answer expectations:
- should mention both config and docs, or both touched files

### Case 3 — add_readme_environment_section

Purpose:
- realistic inspect-then-document task
- tests using file contents as source of truth instead of inventing details

Fixture:
- `README.md`
- `config/sample.env`

Prompt shape:
- asks for a concise README addition based on existing env names
- intentionally allows some wording variation while keeping deterministic checks possible

Deterministic outcome:
- `README.md` gains an `Environment` section
- required env vars from `config/sample.env` are listed
- no invented env var names appear in the added section
- `config/sample.env` remains unchanged

Trace expectations:
- should read `config/sample.env`
- should not modify source env file

Final answer expectations:
- states that an environment section was added to `README.md`

### Case 4 — ambiguous_production_switch_requires_clarification

Purpose:
- realistic ambiguity handling inside a workspace
- tests whether the model avoids unsafe edits and completion claims

Fixture:
- `config/app.toml`
- `config/worker.toml`

Prompt shape:
- requests a production switch without specifying which config
- asks for a brief response

Deterministic outcome:
- workspace remains unchanged

Trace expectations:
- tool use is optional
- if tools are used, they must stay valid and within the workspace

Final answer expectations:
- asks a clarifying question
- makes the ambiguity explicit
- does not claim the change is complete

## Tool subset

Phase 2 should expose this tool set:
- `read`
- `write`
- `edit`
- `ls`

Rules:
- all tool paths must be relative to the ephemeral workspace root
- absolute paths and parent traversal outside the root are invalid
- tool calls must be recorded in structured traces

`find` is not required for the initial Phase 2 case set.

## Scoring

Each workspace case should produce the same benchmark case-level fields used in Phase 1, plus workspace/tool details.

Scoring should combine:
- workspace state correctness
- tool trace validity/quality
- final answer correctness

### Hard deterministic failures

A workspace case should hard-fail if any of these occur:
- invalid tool name
- invalid tool arguments
- path escapes workspace root
- required file outcome is not achieved
- files changed when the case expected no edits
- final answer claims completion when the workspace state does not support that claim

### Rubric-style deterministic checks

If hard-fail conditions do not trigger, use small inspectable checks such as:
- read before edit on target files
- touched only expected files
- final answer mentions the changed file(s)
- final answer reflects the actual workspace result
- answer avoids fabrication

Judge scoring is not required for the initial Phase 2 implementation.

## Result shape extension

Keep the Phase 1 top-level result layout.

Extend it with:
- `summary.categories.quality_with_tools`
- additional per-case fields for workspace/tool cases such as:
  - `kind`
  - `fixture`
  - `tool_trace`
  - `tool_summary`
  - `workspace`

The existing `cases` array remains the main per-case ledger.

## CLI output

Summary output should add one compact section for `quality with tools` showing:
- score
- passed/total cases
- total tool calls
- invalid tool calls

Detailed `bench-show` output should show workspace traces only at the case level, not in the top summary block, to avoid clutter.

## Acceptance criteria

Phase 2 is successful if:
1. It adds realistic workspace-backed cases without changing the benchmark identity.
2. It keeps comparisons stable across model variants.
3. It scores primarily from actual workspace outcomes.
4. It records structured tool traces.
5. It keeps CLI output readable.
6. It avoids drifting back into toy enum/JSON micro-evals for the tool phase.
