# Spec: benchmarking

## Problem

`agentmux` is where local model stacks are actually served for real use, but today there is no simple, repeatable way to compare:
- one mux against another mux
- a full-weight model against its quantized version
- one model family against another

The benchmark we need is not a generic model leaderboard. It is a practical harness-fit benchmark for local agent backends.

The main question is:

> Is this served stack a good candidate for the agent harness, and how does it compare to other candidate stacks?

The benchmark must stay simple:
- run against a real mux by stack name
- produce one result file per run
- make it easy to compare result files later
- show category-level strengths and weaknesses, not just one collapsed score

This tool belongs in this repo only because this repo is the real serving surface for the stacks being compared. Benchmark definitions are not part of mux manifests.

## Scope

This spec locks the overall benchmark design. Implementation can be phased, but the design target is:
- a separate benchmark command in `agentmux`
- benchmark execution against a real stack name
- benchmark execution using `.venv-vllm`
- one built-in benchmark profile designed around local agent-harness use
- repeatable measurement of:
  - serving performance
  - VRAM / memory footprint
  - quality without tools
  - quality with tools
  - reliability / anti-garbage signals
- one JSON result file per run
- a human-readable terminal summary
- enough structured detail in the result file to compare runs later
- support for comparing full-weight and quantized variants by running the same benchmark against different muxes
- a workspace-backed tool-evaluation path that can grow into a sandboxed repo/playground simulation
- a future long-context probe that is adjacent to the benchmark but not required to affect benchmark scoring

Out of scope for the initial implementation phases:
- embedding benchmark config in mux manifests
- browser dashboard or web UI
- benchmark result database or server
- large academic eval suites
- proxy-specific benchmarking
- broad generic leaderboards
- a dedicated compare subcommand in the first pass

## Requirements

### 1. Invocation and environment

The benchmark must run against a mux stack by name.

Preferred invocation shape:

```bash
uv run --python .venv-vllm/bin/python agentmux bench <stack>
```

Examples:

```bash
uv run --python .venv-vllm/bin/python agentmux bench qwen3_5_9b
uv run --python .venv-vllm/bin/python agentmux bench qwen3_5_9b_quant
```

Behavior:
- benchmark input is a stack name, not a raw base URL
- the benchmark targets an already-running stack in the initial implementation phases
- later phases may add stack launch/reuse behavior, but the result file must always state how the target stack was obtained
- the benchmark must use the actual stack shape served by `agentmux`
- no benchmark definitions are stored in mux manifests

### 2. Result artifact

Each benchmark run must emit exactly one primary result file.

Preferred location:
- under `~/runs/agentmux/benchmarks/`
- file name should include timestamp, stack name, and benchmark profile name

Preferred shape:

```text
~/runs/agentmux/benchmarks/20260502-153000-qwen3_5_9b-ghosty-local-agent.json
```

The result file must be sufficient for later file-to-file comparison without rerunning the benchmark.

The result file must include:
- benchmark version
- benchmark profile name
- stack name
- stack manifest path
- timestamp
- environment summary
- summary metrics by category
- VRAM / memory-footprint stats for the served stack when available
- overall summary score for quick viewing
- category scores for detailed comparison
- per-case results with enough evidence to audit scores
- benchmark settings used for the run
- judge-model metadata when judge scoring is enabled
- workspace/sandbox metadata when workspace-backed cases are used

### 3. Human-readable summary

The CLI must print a compact summary to the terminal.

The summary must show:
- stack name
- benchmark profile name
- serving metrics summary
- VRAM / memory-footprint summary
- quality-without-tools summary
- quality-with-tools summary
- reliability summary
- overall score
- candidate verdict
- blocking weaknesses, if any

The summary must not hide category performance behind a single number.

### 4. Benchmark profile philosophy

The first built-in benchmark profile should focus on actual harness use.

Proposed name:
- `ghosty-local-agent`

The profile should be inspired by the real usage pattern of `pi-ghosty`, but should remain benchmark-local and not depend on `pi-ghosty` runtime code.

The benchmark should simulate a small local coding/terminal agent backend that:
- follows instructions
- stays concise
- produces valid structured outputs
- uses tools sensibly
- recovers from tool failures
- avoids hallucinating success
- avoids repetitive bad tool behavior

### 5. Category breakdown

The benchmark must report at least these top-level categories:

#### 5.1 Serving

Purpose:
- measure the cost and responsiveness of using the stack locally

Metrics should include:
- time to first token
- total latency
- output tokens per second
- fixed-concurrency throughput at a small number of levels

Locked design choices:
- the first implementation phases should measure a small fixed concurrency set: `1`, `2`, and `4`
- cold-start measurement is not required in the first implementation phases
- serving results must be reported separately from quality results

#### 5.2 VRAM / memory footprint

Purpose:
- measure how much GPU memory the served stack actually occupies so full-weight and quantized variants can be compared on resource efficiency as well as quality and speed

Metrics should include when available:
- used VRAM after model load
- free VRAM remaining
- total VRAM
- derived percentage of GPU memory consumed

Design notes:
- these stats should be captured from observed runtime state rather than estimated from model metadata alone
- the summary should make it easy to compare memory savings between a full model and its quantized variant
- if exact VRAM stats cannot be collected on a run, the result file should record that clearly rather than inventing a value

#### 5.3 Quality without tools

Purpose:
- measure whether the model is a good harness candidate even before tool execution

This category should use practical, bounded tasks such as:
- choosing the correct action from a small set
- asking for clarification when required information is missing
- returning valid JSON with exact required keys
- producing concise terminal-assistant style responses
- identifying missing constraints instead of inventing details
- producing short coding/helpfulness outputs with fixed expectations

This category must emphasize:
- instruction following
- factual discipline
- concise usefulness
- structured output reliability

#### 5.4 Quality with tools

Purpose:
- measure whether the model behaves well as a tool-using local agent

This category should use practical, bounded tasks such as:
- selecting the correct tool from a known set
- producing valid tool arguments
- sequencing tool use sensibly across a short interaction
- using tool results in the final answer
- recovering after a tool error or refusal
- avoiding repeated failing calls and obvious loops

Locked design choices:
- the benchmark should support a workspace-backed tool-evaluation path
- tool-evaluation workspaces should be ephemeral and rooted in a temp directory by default
- the tool harness should be designed so all tool access is confined to the workspace root
- the first implementation phases may start with safer file-oriented tools and later expand to full repo/playground simulation
- the design must support future bash-enabled cases inside a real sandbox, not just a plain temp cwd
- `bwrap` is available on this machine and should be treated as the preferred future sandbox backend for bash-enabled workspace cases

This category must heavily penalize:
- invalid tool names
- invalid or malformed tool arguments
- unnecessary tool calls
- repeating the same failed action without adapting
- claiming completion unsupported by tool results

#### 5.5 Reliability / anti-garbage

Purpose:
- catch models that appear capable but are unsafe or annoying in harness use

Signals should include:
- malformed structured output rate
- invalid tool-call rate
- hallucinated completion or fabricated success claims
- contradiction of tool output or task constraints
- excessive verbosity when concise output is requested
- empty, degenerate, or evasive output rate

This category is not only informational. It should also feed candidate verdict thresholds.

### 6. Quality scoring philosophy

The benchmark must be more than a speed test. It must prevent obviously bad output from scoring well.

Quality scoring should favor simple, auditable methods in this order:

#### 6.1 Deterministic checks first

Use deterministic scoring whenever possible:
- exact match
- normalized match
- JSON/schema validity
- required field presence
- forbidden field absence
- correct tool name match
- valid tool argument checks
- response length caps
- disallowed phrase or behavior checks

This should be the default approach in the early implementation phases.

#### 6.2 Rubric-based checks for bounded practical tasks

For cases that are not exact-match but are still practical and bounded, define explicit rubric checks such as:
- identified the missing information
- asked a clarifying question
- did not invent a path
- did not claim the task was completed
- used tool output in the final answer

These checks should stay simple and inspectable.

#### 6.3 Optional judge-model scoring only where necessary

Some open-ended short tasks may need a judge model.

Locked design choices:
- judge-model scoring is allowed for a small subset of open-ended cases
- deterministic and rubric-based scoring remain primary
- the model under test must never judge itself
- the judge must return structured rubric results, not free-form prose only
- the default judge target should be `gpt-5.4-mini` unless explicitly overridden later
- judge auth should be sourced from `/home/poop/.pi/agent/auth.json` rather than introducing benchmark-specific tokens into this repo
- the result file must record whether judge scoring was enabled, which judge model was used, and which cases used it
- if judge auth or judge configuration is unavailable, the benchmark should still be able to run without judge-scored cases

Judge-model scoring must not dominate the benchmark.

### 7. Category scores and overall score

The benchmark must provide both:
- an overall score for quick viewing
- category-level scores for real comparison
- explicit VRAM / memory-footprint reporting for resource comparison

Required reporting shape:
- overall summary score
- per-category scores
- sub-metrics within categories
- per-case evidence when needed

The benchmark must not collapse everything into one score.

The intended use is to support questions like:
- is this quant close to the full model overall?
- how much VRAM does the quant actually save versus the full model?
- is this model faster but worse at tool discipline?
- is this model strong without tools but weak with tools?
- does this model stay usable in the harness despite lower throughput?

### 8. Cross-model and quant comparison support

The benchmark must make comparison easy by keeping:
- the benchmark profile fixed
- the case set fixed
- the scoring rules fixed
- the output file format fixed

That way the user can benchmark:
- full model A
- quant model A
- full model B
- quant model B

and compare the resulting files directly.

A dedicated compare subcommand is not required in the first implementation phase, but the JSON shape must support future comparison tooling.

### 9. Candidate verdict

The benchmark must provide a simple verdict for harness suitability.

Suggested verdict shape:
- `recommended`
- `usable_with_tradeoffs`
- `not_recommended`

The verdict must be based on both score and failure thresholds.

A model must not receive a good verdict solely because it is fast or because one aggregate score is high.

Examples of blocking weaknesses:
- invalid tool-call rate above threshold
- malformed structured output rate above threshold
- fabricated success claims above threshold
- repeated failure to recover from tool-error scenarios

The summary must show blocking weaknesses explicitly.

### 10. Simplicity constraints on implementation

The early implementation phases must stay small and practical.

That means:
- one built-in benchmark profile is enough
- a modest number of cases is enough
- simple deterministic/rubric scoring is preferred
- avoid over-modeling benchmark configuration
- avoid framework design for many future benchmark families
- avoid embedding benchmark metadata into mux manifests

A good first pass is one that is clearly useful for deciding whether a local stack is a good harness candidate and for comparing that stack against its quantized version.

### 11. Workspace and sandbox-forward design

The benchmark should be able to evolve toward a more realistic repo/playground simulation without redesigning the core command surface or result format.

Design requirements:
- workspace-backed cases should operate on ephemeral copies of small benchmark fixtures
- the benchmark should be able to preserve workspaces optionally for debugging and audit
- tool traces should be recorded in a structured form when workspace-backed cases are used
- future bash-enabled cases should run inside a real sandbox boundary rather than assuming temp cwd alone is safe enough
- `bwrap` should be the preferred future sandbox backend on this machine unless a better local sandbox path is chosen later

### 12. Long-context as an adjacent future probe

Long-context behavior matters, especially for heavy system prompts and sustained harness sessions, but it is orthogonal to the core benchmark score.

Design requirements:
- the benchmark design should leave room for a future long-context probe
- the long-context probe may live as a flag or as a separate command later
- long-context results do not need to affect the main benchmark score in the first implementation phases
- result-file design should remain compatible with linking or comparing long-context probe results later

## Constraints

- Use `.venv-vllm` for benchmark execution.
- The benchmark must work against actual mux stacks served from this repo.
- The benchmark should reflect real local harness usage more than generic LLM evaluation.
- The benchmark must be simple enough to run routinely when comparing full and quantized variants.
- Result files must remain understandable without needing a separate viewer.
- The benchmark should prefer stable, repeatable scoring over broad or flashy coverage.
- The benchmark must avoid scoring inflation from verbosity, unsupported claims, or pseudo-agentic garbage output.
- The design must leave room for phased implementation: a minimal benchmark first, then richer workspace and sandbox behavior without redesigning the output format or command surface.
- Long-context testing is important but orthogonal; the design should leave room for a future long-context probe without requiring it to affect benchmark scoring.

## Acceptance Criteria

A first useful implementation satisfies this spec if:

1. A user can run a benchmark against a real stack with a single command using `.venv-vllm`.
2. The benchmark emits one primary JSON result file for the run.
3. The CLI prints a compact summary with:
   - overall score
   - category scores
   - candidate verdict
   - blocking weaknesses
4. The result file contains enough detail to compare one model run against another later without rerunning.
5. The benchmark clearly separates:
   - serving
   - VRAM / memory footprint
   - quality without tools
   - quality with tools
   - reliability / anti-garbage
6. The benchmark includes quality logic that prevents obviously bad output from appearing strong due to speed or verbosity.
7. A user can run the same benchmark against a full-weight stack and its quantized stack and inspect whether performance is roughly preserved overall and by category.
8. A user can inspect category-level differences and identify where one model excels or struggles.
9. Benchmark config is not embedded in mux manifests.
10. The implementation remains simple enough that the benchmark feels like a normal repo tool, not a separate benchmark framework.

## Locked Decisions

- `agentmux bench <stack>` targets an already-running stack in the initial implementation phases.
- Judge-model scoring is allowed, but only for a small subset of open-ended cases.
- The default judge target should be `gpt-5.4-mini` unless explicitly overridden later.
- Judge auth should be sourced from `/home/poop/.pi/agent/auth.json`.
- Tool-quality evaluation should grow toward a real workspace-backed repo/playground simulation.
- The design must support future bash-enabled tool cases, but only inside a real sandbox boundary.
- `bwrap` is available and should be treated as the preferred future sandbox backend for bash-enabled cases.
- Fixed serving concurrency levels should start at `1`, `2`, and `4`.
- VRAM / memory-footprint stats should be captured and reported when available so full models and quants can be compared on resource savings.
- Cold-start measurement is deferred.
- File-level comparison is enough for the first pass; browser/file-picker comparison is a future follow-up.
- Long-context testing is important but orthogonal to the benchmark score and should be designed as a future adjacent probe rather than forced into the first benchmark phases.

## Open Questions

1. What exact minimal case set should ship in the first implementation phase so the tool is useful immediately without becoming a large eval project?
2. In the first tool-quality phase, which small tool subset should be implemented before bash-enabled sandbox cases arrive?
3. Should the future long-context probe live under `agentmux bench --long-context` or as a separate command surface?
