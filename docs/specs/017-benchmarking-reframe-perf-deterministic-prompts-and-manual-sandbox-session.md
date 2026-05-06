# Spec: benchmarking reframe — vLLM perf + deterministic prompt bench + manual sandbox session

## Status
Draft (replace/retire prior 017 draft if present).

## Intent
Return the benchmark to what it was supposed to be:

- a **simple** way to compare models and quant variants
- with **trustworthy determinism** (no regex/keyword semantic grading)
- while still providing a realistic signal for "agentic usefulness" via tool/workspace outcomes
- and a Phase 3 path for *manual* qualitative evaluation in a safe sandboxed environment

This spec explicitly removes automated semantic “chat quality” scoring. If a check can’t be made
from hard constraints or observable outcomes, it should be **reported** (transcript, trace) not **scored**.

## Non-goals
- A universal judge-free semantic quality grader.
- Endless rubric tuning.
- Turning agentmux into a general eval platform.

---

## Redefined phases (high level)

### Phase 1/2 (together): a single deterministic prompt bench
We keep the existing prompt sets (structured output, instruction following, clarification, helpfulness,
workspace/tool cases), but we change the scoring philosophy:

- **Deterministic means deterministic**:
  - hard format constraints (exact JSON / exact enums / line counts / max sentence counts)
  - tool protocol validity (structured tool calls, valid args, allowed tools)
  - workspace confinement (no path escape)
  - workspace outcome correctness (file diffs / content checks)
- **No semantic rubric scoring** based on keywords/regex (e.g. “asked a clarifying question”, “gave a reason”).
  - These are still useful prompts, but they become *drills* that emit transcripts.

### Phase 3: manual sandboxed session on a faux repo
Phase 3 is a **user-focused** evaluation mode:

- you run a real interactive session using **pi** (with its real system prompt and tools)
- the model is **sandboxed** to a prepared environment (a faux repo + runtime env)
- you feed prompts **manually** (no scripted prompt runner)
- the system captures everything (transcript, tool trace, workspace diffs)
- the environment can be **restored/reset** between sessions

Scoring is not the point in Phase 3. The point is that you can *watch the model work live*, safely.

---

## Bench A: Perf (vLLM-native, wrapped)

### Purpose
Provide trustworthy, comparable perf numbers:
- throughput (tokens/sec)
- latency / TTFT distributions
- error rate
- (optionally) resource metrics already captured by agentmux (VRAM, etc.)

### Method
Use vLLM’s existing benchmark tooling (OpenAI-compatible serving benchmarks / throughput benches)
via a thin agentmux wrapper.

### Output
- raw vLLM benchmark outputs (unchanged)
- an agentmux wrapper JSON that records:
  - mux/stack identity
  - vLLM args used
  - base_url
  - timestamps
  - pointers to raw vLLM outputs

### Scoring
None. This bench is numbers-only.

---

## Bench B/C: Deterministic prompt bench (agentmux)

This is one bench run that includes:
- workspace/tool cases (what used to be Phase 2)
- no-tools prompt drills (what used to be Phase 1 “quality”)

### What gets scored (pass/fail)
Only deterministic checks:

#### 1) Structured output / format constraints
Examples:
- response parses as JSON
- exact enum match
- exactly N bullet lines and nothing else
- exactly N numbered lines and nothing else
- max sentences / max characters (where specified)

#### 2) Workspace/tool protocol validity
- tool calls are in structured `tool_calls` (not in free-text tool markup)
- tool arguments parse as JSON
- tool is in the allowlist
- tool path resolution cannot escape the workspace root

#### 3) Workspace outcome correctness
- required changes exist (content checks)
- forbidden changes do not exist (changed file set checks)
- deterministic file checks pass

### What does *not* get scored
- semantic adequacy of the prose (helpfulness, “reasoning quality”, “asked a clarifying question”, etc.)

Those prompts are still run, but the output is treated as a transcript to scan.

### What gets reported
For every prompt (workspace or no-tools):
- prompt
- response (and optional thinking)
- usage
- deterministic violations (if any)
- for workspace: tool trace + changed_files + file checks

### Result shape
- Per-case:
  - `passed` is only about deterministic constraints/outcomes
  - `failures` must map to concrete, inspectable evidence
- Run-level:
  - counts of passed/failed deterministic cases
  - summary of tool protocol failures (if any)

---

## CLI: keep it simple

The default CLI should remain a single entry point that prints a compact report with sections:

1) **perf (vLLM)**
2) **deterministic prompt bench**
   - workspace/tool outcome cases: pass/fail counts + notable hard failures
   - drills: constraint failures count (if any)
   - pointer(s) to full transcripts/traces

Implementation may internally call separate modules, but the user-facing workflow is one command.

(We can still keep optional subcommands later, but simplicity is the priority.)

---

## Phase 3: manual sandboxed pi session (design requirements)

### Purpose
A repeatable way to evaluate real agent behavior without trying to auto-score semantics.

### Requirements
- Provide a **faux repo / workspace environment** that feels like real work:
  - real files
  - runnable commands
  - realistic constraints
- The model runs via **pi** (not the bench harness), with pi’s system prompt + tools.
- The environment must be **safe** even if you run pi in YOLO normally.
- The environment must be **resettable**:
  - easy restore to a clean baseline between sessions

### Captured artifacts
- full transcript
- tool trace (as provided by pi)
- workspace diff and/or snapshots
- optional deterministic checks (only if cheap and robust)

### Non-requirements
- automatic qualitative scoring
- automatic prompt scripting (you feed prompts manually)

---

## Phase 3: locked design details

### Sandbox boundary
- Use **bubblewrap (`bwrap`)**.
- **Network access is enabled** inside the sandbox.
- All pi tools are allowed (including bash), with safety coming from filesystem confinement.

### Repo/workspace model
- The Phase 3 scenario runs inside a *real repo working tree*.
- The user-maintained “source” repo lives under:
  - `~/code/bench/<repo>` (or similar; exact repo name is user-chosen)
- Each manual session runs in a **disposable working copy** created from the source repo.
  - Proposed session root:
    - `~/runs/agentmux/bench-sessions/<timestamp>-<repo>/worktree`
  - Reset/teardown is achieved by deleting the session working tree (no history rewriting required).
  - The user is free to commit, branch, and experiment inside the session worktree.

### Environment
- The repo contains its own `.venv/`.
- `.venv` should be **prebuilt** (outside the sandbox is fine); it must be accessible inside the sandbox.

### Artifacts captured (always)
Stored under the session root in `~/runs/agentmux/bench-sessions/<id>/`:
- full transcript
- tool trace
- workspace diff vs session baseline (at minimum `git diff`)
- a short git summary (recommended: `git status`, `git log --oneline -n 20`)

### bwrap mount policy (safety)
- Bind-mount the session worktree as **read-write**.
- Provide an isolated tmp (`tmpfs` or private `/tmp`).
- Avoid granting write access to the rest of `$HOME` by default.
- Minimal read-only binds for system runtime (e.g. `/usr`, `/lib*`, `/bin`) as needed.

---

## Migration notes
- Existing benchmark output files should remain readable.
- We will:
  - remove/ignore semantic rubric failures that depend on keyword/regex heuristics
  - keep deterministic failures and workspace evidence
  - keep transcripts for drill prompts
