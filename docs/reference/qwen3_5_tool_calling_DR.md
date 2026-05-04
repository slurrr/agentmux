---
title: "Qwen3.5 Tool Use Template Issues"
source: "https://gemini.google.com/app/447e92a5a37a2c98"
author:
published:
created: 2026-05-04
description: "Gemini conversation with 4 messages"
tags:
  - "clippings"
---
## 1\. Architectural Context and Problem Definition

The deployment of large language models featuring integrated latent deliberation phases—often referred to natively as "thinking" models—presents an intricate array of challenges when interfaced with strict, OpenAI-compatible application programming interfaces (APIs). The Qwen3.5-9B architecture represents a significant evolution in this paradigm. Utilizing a unified vision-language foundation, early fusion training, and an efficient hybrid architecture composed of Gated Delta Networks combined with sparse Mixture-of-Experts, the model is engineered to deliver high-throughput inference with minimal latency. Crucially, its training distribution heavily biases toward emitting a sequential cognitive trace prior to finalizing an outward-facing response. This trace is encapsulated within specific control tokens, canonically `<think>` and `</think>`.  

Serving this model via vLLM 0.20.0 necessitates the use of a dual-parser extraction system. To maintain OpenAI compatibility while exposing the latent logic, vLLM utilizes a deliberation parser to segregate the internal trace into a dedicated API field (traditionally `reasoning_content` or `reasoning`, depending on the specific API middleware version), while a secondary tool parser is deployed to extract actionable XML or JSON tool invocations from the residual text stream.  

The operational tension detailed in the present environment arises from a fundamental software incompatibility between the model’s stochastic, autoregressive generation behavior and the deterministic, linear expectations of the vLLM 0.20.0 parsing pipeline. As observed in empirical testing, deploying the baseline model author’s chat template yields functional standard dialogue but catastrophic failure during tool execution. Conversely, utilizing heavily modified custom templates—designed specifically to force tool extraction—resolves the tool execution failures but severely breaks standard dialogue, causing the model’s substantive output to be swallowed by the deliberation field while leaving the visible response empty.  

This research report provides an exhaustive, component-level architectural diagnosis of this failure mode. By dissecting the interaction between the Jinja chat template topography, the vLLM detokenization pipeline, the generation prompt, and the specific parser configurations, the underlying causes are isolated. Furthermore, this report evaluates and ranks plausible, implementation-ready architectural strategies tailored for vLLM 0.20.0 that preserve the latent cognitive trace independently of the final output, explicitly avoiding destructive merging or capability-suppression techniques.

## 2\. Diagnosing the Failure Modes

To resolve the severe discrepancy between standard dialogue and tool-use generation, it is imperative to deconstruct how the model emits sequential tokens and how the vLLM middleware intercepts, buffers, and routes those tokens. The failure mode is not a singular software bug but a compound interaction between the text generation prompt, the model's structural tendency to embed tools within its own cognitive trace, and the rigid boundaries enforced by downstream extractors.

### 2.1 The Linear Parsing Bottleneck: Why the Author Template Fails Tool Use

The model author's default chat template operates under the implicit assumption of a strict chronological sequence during text generation. The expected sequence is as follows:

1. The user prompt is parsed and tokenized.
2. The model initiates a `<think>` block.
3. The model completes its internal deliberation.
4. The model emits a `</think>` token.
5. The model subsequently generates the final text response or a tool invocation.

When a user prompt requires no external tools, the model naturally follows this sequence. The vLLM deliberation parser (specifically the `qwen3_reasoning_parser` inherited from `BaseThinkingReasoningParser`) monitors the token stream. It triggers a state transition upon detecting the `</think>` token, effectively slicing the output string. Everything preceding the token is routed to the distinct `reasoning` field, and everything subsequent is routed to the standard `content` channel. Because no tools are required, the `content` channel populates normally, and the standard chat succeeds.  

However, the architecture of Qwen3.5 exhibits a strong, natively trained tendency to embed XML tool calls *inside* the deliberation trace when executing complex agentic tasks. When a tool call is generated before the closing `</think>` token, the standard parsing sequence undergoes a catastrophic collapse. The interaction fails due to the linear isolation of the vLLM parsing pipeline:  

1. **The Deliberation Extractor:** The `qwen3` parser aggressively buffers the entire text block, including the trapped `<tool_call>` elements, because the terminal `</think>` token has not yet been emitted. It routes the entirety of the text to the `reasoning` field.
2. **The Downstream Tool Parser:** The secondary tool parser (whether `qwen3_coder` or `qwen3_xml`) is architected to exclusively inspect the standard `content` channel.

Because the tool invocation string was completely consumed by the preceding deliberation parser, the tool extractor receives an empty string. The vLLM engine assumes no tools were called and terminates the generation cycle. The resulting OpenAI-compatible response contains a populated `reasoning` field but an empty `tool_calls` array, resulting in a silent failure where the agent loop stalls. The bug is not that vLLM forces Qwen3.5 to generate tools inside the trace; the bug is that the standard vLLM 0.20.0 pipeline does not recover or promote those tools when that output pattern natively occurs.  

### 2.2 The Custom Template Collapse: Why No-Tool Answers Land in the Deliberation Trace

To circumvent the swallowed tool-call phenomenon, developers and operators often turn to custom templates, the most prominent being the `qwen3.5-enhanced.jinja` template. This template forces the tool parser to recognize invocations by fundamentally altering how the `<think>` and `</tool_call>` boundaries are constructed in the context window. Specifically, it implements an interleaved-thinking framework that treats unclosed deliberation blocks as plain text, tricking the tool parser into executing even if the model forgets to emit the `</think>` token, or intentionally leaking the context.  

While this custom template forces tool stability in long-context agentic loops, it actively destroys the standard, no-tool chat functionality. The mechanism of this destruction lies in the manipulation of the conditional closing of the deliberation phase. The custom template alters the generation prompt and system instructions such that the model frequently outputs its substantive, final answer without ever emitting a terminal `</think>` tag.

Because the vLLM `qwen3` reasoning parser is a stateful stream evaluator explicitly designed to buffer generated tokens into the deliberation field until the exact `</think>` string is matched, a missing closing tag causes the buffer to remain open indefinitely. Consequently, the parser captures the entire generated response—including the final user-facing text answer—and locks it permanently inside the internal trace field. The `content` field, which sits idle awaiting tokens that follow the missing closing tag, receives nothing.  

The OpenAI-compatible client thus receives an empty `content` string, while the entire substantive reply is hidden within the diagnostic trace data. This precisely explains the observed failure mode: the custom setup yields empty responses for no-tool prompts because the template's structural distortion prevents the state machine of the reasoning parser from executing its closure protocol.  

### 2.3 Template Shape vs. Generation Prompt vs. Parser Contract

To directly address the diagnostic parameters of the serving environment, the issue is not isolated to a single component; it is a fundamental mismatch between the chat-template shape, the generation prompt, and the strict reasoning parser contract.

| **Component** | **Operational Logic** | **Contribution to the Failure Mode** |
| --- | --- | --- |
| **Model Expected Format** | Trained on pure `<think>` tags, frequently intermingling executable actions with latent reasoning steps. | The model assumes downstream systems can interpret an XML action regardless of its position relative to the reasoning boundaries. |
| **Parser Contract** | vLLM 0.20.0 operates a rigid, isolated, and sequential detokenization pipeline. The reasoning parser owns everything before `</think>`. | The strict isolation ensures that any action trapped inside the reasoning buffer is mathematically invisible to the tool parser, creating a silent drop. |
| **Custom Template Shape** | Injects prompt engineering to force unclosed blocks or alters tag sequences to bypass the parser isolation for tools. | By mangling the baseline token topography to save tool calls, it invariably disrupts the model's standard autoregressive pathways, causing it to omit terminal tags during standard conversation. |

 

The hybrid XML/OpenAI template attempts to solve a middleware parsing deficiency using prompt-layer injection. By mangling the template to force the model to output tool tags outside the trace, it disrupts the delicate statistical equilibrium required for standard text generation. A permanent, enterprise-grade solution cannot rely on template hacks that alter the fundamental token boundaries; it must address the parser interaction directly or utilize a template that strictly enforces the model's native formatting without structural distortion.

## 3\. Tool Extraction Mechanics: Comparing vLLM Parsers

The vLLM 0.20.0 framework provides multiple parsing modules designed to extract actionable structured data from continuous text streams. For the Qwen3.5-9B architecture, two primary tool parsers are natively supported and frequently utilized: `qwen3_coder` and `qwen3_xml`. Selecting the correct extraction paradigm is critical for operational stability, as their internal algorithms respond differently to malformed text and unclosed deliberation blocks.  

### 3.1 The Streaming Regex Paradigm (`qwen3_coder`)

The `qwen3_coder` parser represents the older, heavily recommended default for Qwen-series models. It is designed as a streaming regular expression (regex) evaluator.  

- **Operational Mechanism:** As delta tokens stream from the inference engine, the parser continuously evaluates the text against predefined regex patterns to identify function names and parameter boundaries (e.g., `<function=fn><parameter=x>val</parameter></function>`).
- **Vulnerabilities:** While highly aggressive and capable of catching tool calls quickly, regex-based parsing over continuous natural language is notoriously brittle. If a tool call parameter contains strings that mimic structural tags—such as mathematical operators in code blocks (e.g., `if (a < b)`)—the regex engine interprets the `<` character as the beginning of an XML tag. This instantly corrupts the extraction sequence, resulting in dropped parameters or fatal parser crashes during long-context agentic operations.
- **Interaction with Custom Templates:** The custom `qwen3.5-enhanced.jinja` template relies specifically on the `qwen3_coder` parser because its aggressive streaming nature allows it to sometimes trigger a tool extraction even when the preceding `<think>` tag remains unclosed. However, this "bug-plus-bug" interaction is highly unstable and prone to infinite loops.

### 3.2 The Expat XML Registry Paradigm (`qwen3_xml`)

The `qwen3_xml` parser represents a structural upgrade for handling complex, multi-parameter tool calls. It utilizes an Expat-based XML parsing engine rather than regex pattern matching.  

- **Operational Mechanism:** This parser operates as a deferred, registry-based evaluator. It buffers the incoming text stream and relies on strict XML well-formedness to extract elements defined within `<tool_call>` boundaries. It waits until a complete parameter block is received before executing JSON conversion logic (`json.loads`), ensuring that multi-line or complex strings are handled correctly.
- **Vulnerabilities:** Because it enforces strict XML evaluation, it is entirely dependent on receiving an intact string. If the upstream deliberation parser consumes half of the XML tag, the `qwen3_xml` parser will silently discard the fragment.
- **Advantages in Production:** For long-context agentic work (e.g., surpassing 50,000 tokens), the `qwen3_xml` parser is empirically more stable. It natively handles code blocks, mathematical operators, and complex JSON arrays embedded within parameters without corruption. Furthermore, it incorporates auto-healing routines for minor XML malformations, preventing the pipeline from crashing during complex workflows.

### 3.3 Parser Comparison Matrix

| **Feature / Capability** | **qwen3\_coder (Regex-based)** | **qwen3\_xml (Expat-based)** |
| --- | --- | --- |
| **Parsing Mechanism** | Continuous regex stream evaluation. | Deferred XML registry evaluation. |
| **Expected Syntax** | `<function=fn><parameter=x>val</parameter>`. | `<tool_call>{"name": "fn", "arguments": {...}}</tool_call>`. |
| **Resilience to Code Syntax** | Low. Prone to crashing on `<` or `>` operators. | High. Safely evaluates complex nested strings. |
| **Requirement for Closed Tags** | Low. Can aggressively parse broken streams. | High. Requires structurally intact XML blocks. |

 

The technical data strongly indicates that while `qwen3_coder` is occasionally utilized to catch unclosed blocks generated by hacked templates, `qwen3_xml` is vastly superior for production stability, provided the underlying chat template and middleware pipeline are structurally sound.  

## 4\. The Mismatch: Native Format vs. Hybrid OpenAI Template

Beyond the parser mechanics, a critical source of instability stems from attempting to force the Qwen3.5 native architecture into a strict OpenAI API schema using incompatible Jinja runtimes. The model author's baseline template, while theoretically correct for the model's training distribution, contains specific code execution flaws that manifest catastrophically in vLLM.

### 4.1 Jinja Runtime Incompatibilities

vLLM utilizes a C++ accelerated backend for rapid tokenization and prompt rendering. The official Qwen3.5 Jinja template heavily utilizes Python-specific dictionary iterators, most notably the `|items` filter, to construct tool-call definitions in the system prompt.  

While this template successfully renders in pure Python testing environments, the `|items` iterator fails unpredictably or completely crashes within C++ Jinja runtimes. When this crash occurs during tool-prompt rendering, the model is deprived of its necessary structural instructions, leading directly to the erratic tool behavior observed with the baseline author template. Furthermore, the baseline template blindly applies `|tojson` serialization on argument values, which corrupts the payload if the value is already a string, causing downstream schema validation errors.  

### 4.2 Prefix Caching and Historical Trace Pollution

A secondary factor contributing to prompt mismatch and operational degradation is the handling of multi-turn conversational history. In sophisticated agentic loops, the context window rapidly fills with prior iterations of reasoning and tool execution.

The official Qwen3.6 and Qwen3.5 templates introduced a `preserve_thinking` feature designed to maintain the cognitive trace across turns. However, the baseline implementation is flawed: it wraps past assistant turns in `<think></think>` tags even if the actual `reasoning_content` is completely empty.  

This behavior causes severe issues in a vLLM 0.20.0 environment:

1. **Context Pollution:** The context window is spammed with empty tags, consuming token limits and distracting the model's attention mechanism.
2. **Prefix Caching Degradation:** vLLM relies heavily on prefix caching (Automatic Prefix Caching and Mamba cache align modes) to reduce Time-To-First-Token (TTFT) during long agentic runs. When the template retroactively injects empty `<think>` scaffolding into historical turns, it alters the serialized prompt signature. This causes avoidable cache misses and forces the engine to redundantly process equivalent histories, destroying inference efficiency.
3. **Template Crashes on Tool Results:** The baseline templates scan for the last "real" user query. In dense agentic loops where the message list ends with tool results rather than a direct user message, the template hard-crashes with a `raise_exception`, terminating the inference request entirely.

The custom `qwen3.5-enhanced.jinja` template bypasses some of these caching issues by mandating `preserve_thinking=false` , but in doing so, it strips the model of vital historical context, forcing it to re-deduce complex states from scratch.  

## 5\. Evaluated Solution Paths Ranked by Realism

Based on the exhaustive architectural constraints of vLLM 0.20.0, the non-negotiable necessity of preserving the cognitive trace separately, and the requirement to support both tool and no-tool requests flawlessly, the following solution paths are proposed. They are ranked from the most permanent and structurally sound to the least desirable fallback strategies.

### 5.1 Path 1: Backend Parser Promotion (Optimal Software Architecture)

**Diagnosis:** The most definitive and structurally sound cause of the failure mode is the linear isolation of the vLLM parsing pipeline. The model accurately follows its training distribution by embedding executable `<tool_call>` markup inside the `<think>` trace block, but the downstream software discards it.  

**The Solution:** The optimal architecture involves leveraging the software patch introduced in vLLM Pull Request #39055 ("Fix Qwen3 reasoning tool calls embedded inside think"). This patch fundamentally refactors the logic within the `vllm/reasoning/qwen3_reasoning_parser.py` module.  

Instead of operating as a blind buffer that routes all internal text exclusively to the `reasoning` field, the upgraded parser continuously monitors the stream for embedded XML tool-call schemas. When it detects a `<tool_call>` boundary existing *inside* the deliberation trace, it systematically promotes that specific XML block out of the `reasoning` buffer and injects it into the standard `content` buffer.  

Once the tool string is promoted to the `content` buffer, the downstream tool parser (specifically `qwen3_xml`) functions flawlessly, successfully mapping the arguments into the OpenAI `tool_calls` schema array.  

**Implementation:** This requires ensuring the vLLM 0.20.0 deployment incorporates this PR. If the standard 0.20.0 image lacks the merged patch, a custom Docker build or manual patch of the `qwen3_reasoning_parser.py` file is required. Once implemented, the deployment can utilize a strictly sanitized standard chat template.

| **Pros** | **Cons** |
| --- | --- |
| **Total Resolution of No-Tool Bug:** Entirely eliminates the "empty response" error, as standard templates can be used, ensuring `</think>` is always emitted normally. | **Infrastructure Dependency:** Requires intervention at the Python backend level if the specific container image in use does not yet contain the merged PR #39055. |
| **Trace Preservation:** Preserves the latent cognitive trace exactly as intended, fulfilling the core constraint without destructive merging. | **Maintenance Overhead:** Custom patches must be tracked across future vLLM version upgrades. |
| **Zero Prompt Hacking:** Requires zero prompt engineering, context distortion, or template manipulation to force tool extraction. |  |

 

### 5.2 Path 2: Strict Template Sanitization with XML Parsing (Optimal Configuration Fix)

If modifying the vLLM Python backend is restricted by organizational or infrastructure constraints, the next best architectural path focuses on resolving the template topography.

**The Solution:** Immediately discard the flawed `qwen3.5-enhanced.jinja` template. Implement the rigorously validated `froggeric/Qwen-Fixed-Chat-Templates` (specifically utilizing the `qwen3.6/chat_template.jinja`, which maintains full backwards compatibility and structural fixes for Qwen3.5-9B).  

Unlike the "enhanced" templates that intentionally break closing tags to force aggressive stream extraction, the `froggeric` template focuses strictly on resolving the runtime bugs inherent in the model author's baseline code.  

This template introduces critical operational stability improvements:

1. **Runtime Stability:** It replaces the Python `|items` iterators with compatible direct key lookups, preventing silent C++ Jinja engine crashes during complex tool argument parsing.
2. **Context Sanitization:** It utilizes conditional logic on `reasoning_content` to absolutely prevent the generation of empty `<think></think>` blocks in historical turns. This single fix restores prefix cache integrity and drastically lowers Time-To-First-Token in deep agentic loops.
3. **Role Management:** It safely handles empty tool output payloads and natively maps modern `developer` roles to the legacy `system` role, preventing API rejections from stringent middleware.

By utilizing this sanitized template in conjunction with the robust `--tool-call-parser qwen3_xml` flag , the model is provided with the cleanest possible prompt topography. The model is statistically encouraged to cleanly terminate the deliberation phase *before* emitting the tool call, drastically reducing the instances of embedded XML that trigger the parser drop.  

| **Pros** | **Cons** |
| --- | --- |
| **Restores Standard Chat:** Resolves the no-tool empty response bug because the template strictly enforces the native `</think>` token boundaries without manipulation. | **Statistical Edge Cases:** Because it does not alter the underlying parsing pipeline, there remains a marginal statistical chance that the model may hallucinate a tool call inside the trace block during extraordinarily complex workflows. |
| **Deployment Simplicity:** Implemented entirely via the `--chat-template` command-line argument without altering the vLLM source codebase. | **Parser Strictness:** The `qwen3_xml` parser requires well-formed output; severe model hallucinations can still cause validation drops. |
| **Robust Extraction:** The `qwen3_xml` parser provides superior recovery against nested JSON or code syntax compared to the regex-based `qwen3_coder` parser. |  |

 

### 5.3 Path 3: Asymmetric Middleware Routing (Fallback Architectural Fix)

If the deployment environment strictly prohibits backend software patches, and the sanitized template approach still yields unacceptable variances in tool-call reliability due to the model's stochastic nature, the final architectural path is asymmetric routing.

**The Solution:** This architecture operates on the principle that tool-enabled queries and standard dialogue queries possess fundamentally incompatible optimal token topographies within an unpatched vLLM pipeline. A lightweight middleware proxy (such as LiteLLM or an internal Nginx router) is deployed to intercept the incoming OpenAI API request prior to reaching vLLM.

- **Tool Execution Route:** If the middleware detects that the `tools` array is populated in the request payload, the request is routed to a dedicated vLLM worker instance running the `qwen3.5-enhanced.jinja` template and the `qwen3_coder` parser. This configuration guarantees tool extraction via aggressive stream interception, effectively sacrificing standard chat stability for tool reliability.
- **Standard Chat Route:** If the `tools` array is empty, the request is routed to a separate vLLM worker instance running the sanitized `froggeric` template and lacking a tool parser. This guarantees perfect deliberation extraction and flawless, high-fidelity standard text responses.

| **Pros** | **Cons** |
| --- | --- |
| **Guaranteed Reliability:** Provides a 100% guarantee of success for both operational modes without requiring any underlying framework patches or waiting for upstream PR merges. | **Resource Inefficiency:** Highly inefficient, requiring doubled VRAM allocation to host redundant models or complex dynamic LoRA/template swapping architectures. |
| **Optimized Sampling:** Allows the deployment of distinct sampling parameters (e.g., higher temperature for creative standard chat, zero temperature for deterministic tool execution). | **Operational Complexity:** Vastly increases infrastructure complexity, latency via middleware hops, and maintenance overhead. |

## 6\. Implementation Strategy for the Serving Environment

Based on the architectural evaluations, Path 2, deployed with concurrent verification of Path 1 components, offers the highest probability of immediate success in the specified vLLM 0.20.0 serving environment.

The custom `qwen3.5-enhanced.jinja` template currently deployed is definitively the root cause of the empty response failures on no-tool prompts, as it actively manipulates the `</think>` boundary. To resolve this discrepancy while strictly adhering to the constraint of preserving the separate cognitive trace, the following configuration protocol must be applied.

### 6.1 Immediate Action Plan

1. **Template Replacement:** Immediately remove the `qwen3.5-enhanced.jinja` template from the server launch configuration. Download the `chat_template.jinja` from the `froggeric/Qwen-Fixed-Chat-Templates` repository. This template corrects the API role mappings and C++ iterator crashes without manipulating the fundamental trace boundaries required for proper no-tool prompt execution.
2. **Parser Alignment:** Reconfigure the vLLM startup flags to utilize the Expat-based XML parser, which is structurally more stable for Qwen deployments than the legacy regex variant. Execute the server with the following aligned parsers: `--tool-call-parser qwen3_xml` `--reasoning-parser qwen3`
3. **Chat Template Arguments:** To ensure the model does not enter infinite deliberation loops, maintain efficient prefix caching, and avoid the historical trace pollution bug, pass the following argument to the launch script : `--default-chat-template-kwargs '{"preserve_thinking": false}'`
4. **Backend Verification:** Inspect the deployed vLLM 0.20.0 Python environment to verify if the logic from PR #39055 is present in `vllm/reasoning/qwen3_reasoning_parser.py`. If the environment permits, manually applying this promotion logic will mathematically guarantee that even if a tool call slips into the cognitive trace stochastically, it will be seamlessly extracted and executed.

### 6.2 Secondary Stability Variables: Precision Drift and Hardware Synchronization

When operating models of this parameter class, secondary hardware and framework variables frequently masquerade as parser or template failures. If the deployment experiences tool-calling failures that appear silently after extended context generation (e.g., past 30,000 to 50,000 tokens), it is highly probable that the root cause is precision drift rather than a template mismatch.  

If the vLLM deployment utilizes a mixed-GPU topology (e.g., disparate NVIDIA architectures spanning SM80 and SM89 generation cards), tensor parallelism will split matrix multiplications across differing native precisions. For example, an RTX 4090 will execute using native FP8 W8A8 tensor cores, while an older RTX 3090 will fall back to W8A16. This architectural discrepancy results in mismatched intermediate calculation results that accumulate over long conversations. Eventually, this drift causes the model's output logits to degrade, producing malformed XML tags that the strict `qwen3_xml` parser cannot decipher, resulting in a silent pipeline failure.  

To stabilize the generation formatting at high context depths, uniform precision computation must be enforced across the cluster.

**Hardware Configuration Fixes:**

- Define the environment variable `VLLM_TEST_FORCE_FP8_MARLIN=1`. This forces the newer architecture to down-step and match the precision of the older architecture, eliminating output drift.
- Ensure that PCIe inter-node communication is stabilized by applying `NCCL_P2P_DISABLE=1` and `NCCL_ALGO=Ring`. While these are low-level NVIDIA Collective Communications Library optimizations, they directly impact the lexical stability of the strings generated by the model under heavy tensor-parallel load.

## 7\. Synthesized Conclusions

The specific failure mode currently restricting the vLLM 0.20.0 deployment—where no-tool prompts yield empty API responses while substantive conversational output is trapped inside the diagnostic deliberation field—is an artificial anomaly introduced by the custom XML template. By actively obfuscating the end-of-trace token in an attempt to force aggressive tool extraction, the custom template inherently prevents the `qwen3` deliberation parser's state machine from correctly transitioning. Consequently, the parser fails to route standard text to the OpenAI `content` field.

Furthermore, the initial failure of the model author’s baseline template during tool-use operations is attributed to a combination of incompatible Jinja rendering iterators crashing the C++ runtime, and the model’s architectural propensity to embed XML invocations inside its own cognitive trace, which blinds the linearly isolated downstream tool parser.

By executing a structural migration to a strictly sanitized chat template that respects native token boundaries (`froggeric/Qwen-Fixed-Chat-Templates`), leveraging the superior `qwen3_xml` extraction parser, and applying backend structural promotion patches (PR #39055), the deployment can achieve total operational stability.

This recommended architecture guarantees the seamless execution of complex, agentic tool workflows and standard dialogue queries simultaneously. Most importantly, it fulfills the core organizational constraint by fully capturing and preserving the model's invaluable latent deliberation process via the strict `reasoning_content` schema, requiring no destructive capability suppression or trace merging.