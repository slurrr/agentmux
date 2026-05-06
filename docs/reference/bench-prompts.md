# Benchmark prompts reference (deterministic)

This document is the canonical prompt reference for the benchmark reframe.

Scoring is deterministic-only:
- hard format constraints
- tool protocol validity
- workspace confinement/outcomes

Semantic prose quality is not scored.

## No-tools drills (`src/agentmux/bench_cases.py`)

### structured_output

- `action_choice_enum`
  - Prompt: return exactly one word from `clarify|search|edit|answer` for missing-file request.
  - Pass criteria:
    - response equals exactly `clarify`

- `exact_json_small_object`
  - Prompt: emit JSON object with `task_type`, `needs_clarification`, `reason`.
  - Pass criteria:
    - valid JSON object
    - exactly those 3 keys
    - `task_type == "edit"`
    - `needs_clarification == true`
    - `reason` is non-empty and under 12 words

- `bounded_structured_summary`
  - Prompt: JSON array of 2 short safe steps.
  - Pass criteria:
    - valid JSON array
    - exactly 2 string items
    - each item under 10 words
    - no completion claim

### instruction_following

- `exactly_three_bullets`
  - Pass criteria:
    - exactly 3 non-empty lines
    - all 3 lines are bullets

- `hard_length_limit`
  - Pass criteria:
    - response length <= 140 chars

- `constrained_task_plan`
  - Pass criteria:
    - exactly 3 non-empty lines
    - all 3 numbered steps
    - each step is one sentence

### clarification

- `missing_path_requires_clarification`
  - Pass criteria:
    - <= 2 sentences
    - no completion claim
    - no invented filename/path

- `ambiguous_destructive_request`
  - Pass criteria:
    - <= 3 sentences
    - no completion/deletion claim

- `insufficient_evidence_no_fabrication`
  - Pass criteria:
    - <= 2 sentences
    - no unsupported certainty claim

### helpfulness drills (deterministic constraints only)

- `short_bug_triage`
  - Pass criteria:
    - <= 4 sentences

- `short_edit_strategy`
  - Pass criteria:
    - <= 4 sentences
    - no invented filename

- `short_terminal_next_step`
  - Pass criteria:
    - <= 3 sentences

## Workspace/tool cases (`src/agentmux/bench_workspace.py`)

All cases require:
- valid structured tool calls (JSON args)
- allowed tool names only
- no workspace path escape
- case-specific file checks
- deterministic failure on non-final stop reasons (`max_turns`, `request_error`, etc.)

Cases:

- `update_api_base_url`
  - Required outcome:
    - `config/app.toml` contains `api_base_url = "https://api.example.com/v1"`
    - only `config/app.toml` changed

- `rename_timeout_key_everywhere_needed`
  - Required outcome:
    - `config/app.toml`: `timeout_secs` -> `request_timeout_secs`, value preserved
    - `docs/config.md`: old key replaced by new key
    - only those two files changed

- `add_readme_environment_section`
  - Required outcome:
    - `README.md` has `## Environment`
    - includes required vars from `config/sample.env`
    - `config/sample.env` unchanged
    - only `README.md` changed

- `ambiguous_production_switch_requires_clarification`
  - Required outcome:
    - workspace remains unchanged
    - no completion claim for ambiguous request
