# Supplemental Spec: M5 v1 contract for `bench-session` (CLI-first)

## Status
Draft supplemental artifact for Phase 3/M5 implementation shaping.

## Scope
Define the v1 contract for manual sandboxed bench sessions as a distinct command surface, separate from deterministic benchmark scoring/perf flow.

---

## Command

```bash
agentmux bench-session <stack> [--repo PATH] [--offline] [--preserve]
```

## Defaults
- `--repo`: `~/code/bench/bench-playground`
- network: enabled
- tool policy: all tools enabled (including browser/web families)
- teardown: enabled
- on failure: preserve session automatically

---

## Lifecycle contract

### 1) Preflight
Fail fast with clear errors if:
- repo path is missing or not a git repo
- `bwrap` is unavailable
- `pi` is unavailable
- stack cannot be resolved

Before launch, emit a summary of:
- stack
- source repo
- session root
- network mode
- teardown mode

### 2) Session creation
Create session root:
- `~/runs/agentmux/bench-sessions/<timestamp>-<stack>/`

Create disposable worktree:
- `<session_root>/worktree/`
- clone/copy source repo into worktree
- source repo remains untouched

Capture baseline artifacts:
- `baseline_git_status.txt`
- optional `baseline_head.txt`

### 3) Sandbox + pi launch
Launch pi inside `bwrap` with:
- read-write bind: session worktree
- isolated tmp
- minimal read-only system binds needed for runtime
- network enabled by default
- `--offline` disables network

Run pi with cwd set to worktree.

### 4) Artifact capture (always attempt)
Write under session root:
- `session.json` (metadata, policy, timestamps, exit status)
- `transcript.*` (best available)
- `tool_trace.*` (best available)
- `git_status.txt`
- `git_log_oneline.txt` (`git log --oneline -n 20`)
- `git_diff.patch`

Any artifact-capture failures must be recorded in `session.json`.

### 5) Teardown
- default: delete session worktree (or full session dir if artifacts are safely retained)
- `--preserve`: keep session
- any run/capture failure: keep session and print path

Final command output should include:
- success/failure
- artifact location
- whether cleanup occurred

---

## Safety guarantees
1. Source repo under `~/code/bench/...` is never modified directly.
2. Writable filesystem scope is confined to the disposable session worktree.
3. Teardown never touches source repo.
4. Failure path preserves evidence by default.

---

## Non-goals for v1
- no pi extension/slash commands yet
- no manifest field for repo path yet (CLI-only repo selection)
- no advanced tool allowlist policy matrix yet

---

## Minimal v1 flags
- `--repo PATH`
- `--offline`
- `--preserve`

Everything else is default-safe and streamlined for quick manual testing.
