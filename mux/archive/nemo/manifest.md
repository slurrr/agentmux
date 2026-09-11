# nemo

Lab-editable AgentMux export for the proven `nvidia--nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4` vLLM serving preset.

AgentMux is the stable serving cockpit. `workspace-vllm` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `nemo`
- Service: `main`
- Container: `agentmux-nemo-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/nemo/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-vllm`
- Preset name: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`
- Backend: `vLLM`
- Image: `localhost/llm-vllm:latest`
- Model identifier/path: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`
- Served model name: `nvidia--nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4`
- Export timestamp: `2026-08-24T18:53:24-06:00`

## Exported files

- `mux.toml` — AgentMux launch recipe.
- `config/vllm-config.yml` — lab-editable copied serving config.
- `config/launch-vllm.sh` — converts the simple copied YAML into vLLM args.
- `config/vllm-args.txt` — static args snapshot for review.

## Complete serving config

```yaml
server:
  host: 0.0.0.0
  port: 5000
  gpu-memory-utilization: 0.95
  max-model-len: 262144
  tensor-parallel-size: 1
  max-num-batched-tokens: 8192
  max-num-seqs: 16
  moe-backend: marlin
  mamba-backend: flashinfer
  mamba-cache-mode: align
  kv-cache-dtype: bfloat16
  enforce-eager: false
  enable-prefix-caching: true
  generation-config: vllm
  reasoning-parser: nemotron_v3
  tool-call-parser: qwen3_coder
  enable-auto-tool-choice: true
  served-model-name: nemo
  trust-remote-code: false
sampling:
  temperature: 1.0
  top-p: 0.95
  stop:
  - <|im_end|>
model_features:
  architecture: NemotronHForCausalLM
  tool_format: xml
  reasoning:
    enabled: true
    start_token: <think>
    end_token: </think>
    suppress_header: null
  stop_tokens:
  - <|im_end|>
  chat_template: "{% macro render_extra_keys(json_dict, handled_keys) %}\n    {%-\
    \ if json_dict is mapping %}\n        {%- for json_key in json_dict if json_key\
    \ not in handled_keys %}\n            {%- if json_dict[json_key] is mapping or\
    \ (json_dict[json_key] is sequence and json_dict[json_key] is not string) %}\n\
    \                {{- '\\n<' ~ json_key ~ '>' ~ (json_dict[json_key] | tojson |\
    \ safe) ~ '</' ~ json_key ~ '>' }}\n            {%- else %}\n                {{-'\\\
    n<' ~ json_key ~ '>' ~ (json_dict[json_key] | string) ~ '</' ~ json_key ~ '>'\
    \ }}\n            {%- endif %}\n        {%- endfor %}\n    {%- endif %}\n{% endmacro\
    \ %}\n{%- set enable_thinking = enable_thinking if enable_thinking is defined\
    \ else True %}\n{%- set truncate_history_thinking = truncate_history_thinking\
    \ if truncate_history_thinking is defined else True %}\n{%- set ns = namespace(last_user_idx\
    \ = -1) %}\n{%- set loop_messages = messages %}\n{%- for m in loop_messages %}\n\
    \  {%- if m[\"role\"] == \"user\" %}\n    {%- set ns.last_user_idx = loop.index0\
    \ %}\n  {%- endif %}\n{%- endfor %}\n{%- if messages[0][\"role\"] == \"system\"\
    \ %}\n    {%- set system_message = messages[0][\"content\"] %}\n    {%- set loop_messages\
    \ = messages[1:] %}\n{%- else %}\n    {%- set system_message = \"\" %}\n    {%-\
    \ set loop_messages = messages %}\n{%- endif %}\n{%- if not tools is defined %}\n\
    \    {%- set tools = [] %}\n{%- endif %}\n{%- set ns = namespace(last_user_idx\
    \ = -1) %}\n{%- for m in loop_messages %}\n  {%- if m[\"role\"] == \"user\" %}\n\
    \    {%- set ns.last_user_idx = loop.index0 %}\n  {%- endif %}\n{%- endfor %}\n\
    {%- if system_message is defined %}\n    {{- \"<|im_start|>system\\n\" + system_message\
    \ }}\n{%- else %}\n    {%- if tools is iterable and tools | length > 0 %}\n  \
    \      {{- \"<|im_start|>system\\n\" }}\n    {%- endif %}\n{%- endif %}\n{%- if\
    \ tools is iterable and tools | length > 0 %}\n    {%- if system_message is defined\
    \ and system_message | length > 0 %}\n        {{- \"\\n\\n\" }}\n    {%- endif\
    \ %}\n    {{- \"# Tools\\n\\nYou have access to the following functions:\\n\\\
    n\" }}\n    {{- \"<tools>\" }}\n    {%- for tool in tools %}\n        {%- if tool.function\
    \ is defined %}\n            {%- set tool = tool.function %}\n        {%- endif\
    \ %}\n        {{- \"\\n<function>\\n<name>\" ~ tool.name ~ \"</name>\" }}\n  \
    \      {%- if tool.description is defined %}\n            {{- '\\n<description>'\
    \ ~ (tool.description | trim) ~ '</description>' }}\n        {%- endif %}\n  \
    \      {{- '\\n<parameters>' }}\n        {%- if tool.parameters is defined and\
    \ tool.parameters is mapping and tool.parameters.properties is defined and tool.parameters.properties\
    \ is mapping %}\n            {%- for param_name, param_fields in tool.parameters.properties|items\
    \ %}\n                {{- '\\n<parameter>' }}\n                {{- '\\n<name>'\
    \ ~ param_name ~ '</name>' }}\n                {%- if param_fields.type is defined\
    \ %}\n                    {{- '\\n<type>' ~ (param_fields.type | string) ~ '</type>'\
    \ }}\n                {%- endif %}\n                {%- if param_fields.description\
    \ is defined %}\n                    {{- '\\n<description>' ~ (param_fields.description\
    \ | trim) ~ '</description>' }}\n                {%- endif %}\n              \
    \  {%- if param_fields.enum is defined %}\n                    {{- '\\n<enum>'\
    \ ~ (param_fields.enum | tojson | safe) ~ '</enum>' }}\n                {%- endif\
    \ %}\n                {%- set handled_keys = ['name', 'type', 'description', 'enum']\
    \ %}\n                {{- render_extra_keys(param_fields, handled_keys) }}\n \
    \               {{- '\\n</parameter>' }}\n            {%- endfor %}\n        {%-\
    \ endif %}\n        {% set handled_keys = ['type', 'properties', 'required'] %}\n\
    \        {{- render_extra_keys(tool.parameters, handled_keys) }}\n        {%-\
    \ if tool.parameters is defined and tool.parameters.required is defined %}\n \
    \           {{- '\\n<required>' ~ (tool.parameters.required | tojson | safe) ~\
    \ '</required>' }}\n        {%- endif %}\n        {{- '\\n</parameters>' }}\n\
    \        {%- set handled_keys = ['type', 'name', 'description', 'parameters']\
    \ %}\n        {{- render_extra_keys(tool, handled_keys) }}\n        {{- '\\n</function>'\
    \ }}\n    {%- endfor %}\n    {{- \"\\n</tools>\" }}\n    {{- '\\n\\nIf you choose\
    \ to call a function ONLY reply in the following format with NO suffix:\\n\\n<tool_call>\\\
    n<function=example_function_name>\\n<parameter=example_parameter_1>\\nvalue_1\\\
    n</parameter>\\n<parameter=example_parameter_2>\\nThis is the value for the second\
    \ parameter\\nthat can span\\nmultiple lines\\n</parameter>\\n</function>\\n</tool_call>\\\
    n\\n<IMPORTANT>\\nReminder:\\n- Function calls MUST follow the specified format:\
    \ an inner <function=...></function> block must be nested within <tool_call></tool_call>\
    \ XML tags\\n- Required parameters MUST be specified\\n- You may provide optional\
    \ reasoning for your function call in natural language BEFORE the function call,\
    \ but NOT after\\n- If there is no function call available, answer the question\
    \ like normal with your current knowledge and do not tell the user about function\
    \ calls\\n</IMPORTANT>' }}\n{%- endif %}\n{%- if system_message is defined %}\n\
    \    {{- '<|im_end|>\\n' }}\n{%- else %}\n    {%- if tools is iterable and tools\
    \ | length > 0 %}\n        {{- '<|im_end|>\\n' }}\n    {%- endif %}\n{%- endif\
    \ %}\n{%- for message in loop_messages %}\n    {%- if message.role == \"assistant\"\
    \ %}\n        {%- if message.reasoning_content is defined and message.reasoning_content\
    \ is string and message.reasoning_content | trim | length > 0 %}\n           \
    \ {%- set content = \"<think>\\n\" ~ message.reasoning_content ~ \"</think>\"\
    \ ~ (message.content | default('', true)) %}\n        {%- else %}\n          \
    \  {%- set content = message.content | default('', true) %}\n            {%- if\
    \ content is string -%}\n                {%- if '<think>' not in content and '</think>'\
    \ not in content -%}\n                    {%- set content = \"<think></think>\"\
    \ ~ content -%}\n                {%- endif -%}\n            {%- else -%}\n   \
    \             {%- set content = content -%}\n            {%- endif -%}\n     \
    \   {%- endif %}\n        {%- if message.tool_calls is defined and message.tool_calls\
    \ is iterable and message.tool_calls | length > 0 %}\n            {{- '<|im_start|>assistant\\\
    n' }}\n                {%- set include_content = not (truncate_history_thinking\
    \ and loop.index0 < ns.last_user_idx) %}\n                {%- if content is string\
    \ and content | trim | length > 0 %}\n                    {%- if include_content\
    \ %}\n                        {{- (content | trim) ~ '\\n' -}}\n             \
    \       {%- else %}\n                        {%- set c = (content | string) %}\n\
    \                        {%- if '</think>' in c %}\n                         \
    \   {%- set c = c.split('</think>')[-1] %}\n                        {%- elif '<think>'\
    \ in c %}\n                            {%- set c = c.split('<think>')[0] %}\n\
    \                        {%- endif %}\n                        {%- set c = \"\
    <think></think>\" ~ c %}\n                        {%- if c | length > 0 %}\n \
    \                           {{- c ~ '\\n' -}}\n                        {%- endif\
    \ %}\n                    {%- endif %}\n                {%- else %}\n        \
    \            {{- \"<think></think>\" -}}\n                {%- endif %}\n     \
    \           {%- for tool_call in message.tool_calls %}\n                    {%-\
    \ if tool_call.function is defined %}\n                        {%- set tool_call\
    \ = tool_call.function %}\n                    {%- endif %}\n                \
    \    {{- '<tool_call>\\n<function=' ~ tool_call.name ~ '>\\n' -}}\n          \
    \              {%- if tool_call.arguments is defined %}\n                    \
    \        {%- for args_name, args_value in tool_call.arguments|items %}\n     \
    \                           {{- '<parameter=' ~ args_name ~ '>\\n' -}}\n     \
    \                               {%- set args_value = args_value | tojson | safe\
    \ if args_value is mapping or (args_value is sequence and args_value is not string)\
    \ else args_value | string %}\n                                {{- args_value\
    \ ~ '\\n</parameter>\\n' -}}\n                            {%- endfor %}\n    \
    \                    {%- endif %}\n                    {{- '</function>\\n</tool_call>\\\
    n' -}}\n                {%- endfor %}\n                {{- '<|im_end|>\\n' }}\n\
    \        {%- else %}\n            {%- if not (truncate_history_thinking and loop.index0\
    \ < ns.last_user_idx) %}\n                {{- '<|im_start|>assistant\\n' ~ (content\
    \ | default('', true) | string | trim) ~ '<|im_end|>\\n' }}\n            {%- else\
    \ %}\n                {%- set c = (content | default('', true) | string) %}\n\
    \                {%- if '<think>' in c and '</think>' in c %}\n              \
    \      {%- set c = \"<think></think>\" ~ c.split('</think>')[-1] %}\n        \
    \        {%- endif %}\n                {%- set c = c | trim %}\n             \
    \   {%- if c | length > 0 %}\n                    {{- '<|im_start|>assistant\\\
    n' ~ c ~ '<|im_end|>\\n' }}\n                {%- else %}\n                   \
    \ {{- '<|im_start|>assistant\\n<|im_end|>\\n' }}\n                {%- endif %}\n\
    \            {%- endif %}\n        {%- endif %}\n    {%- elif message.role ==\
    \ \"user\" or message.role == \"system\" %}\n        {{- '<|im_start|>' + message.role\
    \ + '\\n' }}\n        {%- set content = message.content | string %}\n        {{-\
    \ content }}\n        {{- '<|im_end|>\\n' }}\n    {%- elif message.role == \"\
    tool\" %}\n        {%- if loop.previtem and loop.previtem.role != \"tool\" %}\n\
    \            {{- '<|im_start|>user\\n' }}\n        {%- endif %}\n        {{- '<tool_response>\\\
    n' }}\n        {{- message.content }}\n        {{- '\\n</tool_response>\\n' }}\n\
    \        {%- if not loop.last and loop.nextitem.role != \"tool\" %}\n        \
    \    {{- '<|im_end|>\\n' }}\n        {%- elif loop.last %}\n            {{- '<|im_end|>\\\
    n' }}\n        {%- endif %}\n    {%- else %}\n        {{- '<|im_start|>' + message.role\
    \ + '\\n' + message.content + '<|im_end|>\\n' }}\n    {%- endif %}\n{%- endfor\
    \ %}\n{%- if add_generation_prompt %}\n    {%- if enable_thinking %}\n       \
    \ {{- '<|im_start|>assistant\\n<think>\\n' }}\n    {%- else %}\n        {{- '<|im_start|>assistant\\\
    n<think></think>' }}\n    {%- endif %}\n{%- endif %}"
model_identifier: nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
slug: nvidia--nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4
```

## vLLM args snapshot

```text
--host
0.0.0.0
--port
5000
--gpu-memory-utilization
0.95
--max-model-len
262144
--tensor-parallel-size
1
--max-num-batched-tokens
8192
--max-num-seqs
16
--moe-backend
marlin
--mamba-backend
flashinfer
--mamba-cache-mode
align
--kv-cache-dtype
bfloat16
--enable-prefix-caching
--generation-config
vllm
--reasoning-parser
nemotron_v3
--tool-call-parser
qwen3_coder
--enable-auto-tool-choice
--served-model-name
nemo
```

## Notes / caveats

```text
- [2026-08-24] Onboarded nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 (NemotronHForCausalLM).
- Native context length: 1048576 tokens.
- Selected server config: max-model-len=16384, gpu-memory-utilization=0.9, tensor-parallel-size=1, kv-cache-dtype=int4_per_token_head, enforce-eager=True.
- Runtime/cache plan: confidence=medium, rules_used=['backend_paged_attention_planning', 'explicit_head_dim', 'hf_config', 'quantization_metadata'].
- Tool format: xml.
- Reasoning: enabled <think> ... </think>.
- Sampling source: generation_config.
- Model weights on disk: ~20.08 GB.
- Model shape: 52 layers, 32 heads, 2 KV heads.

- Estimated VRAM requirements (weights: ~20.08 GB):
  * 4k context: ~20.28 GB estimated total VRAM (fits current budget)
  * 8k context: ~20.49 GB estimated total VRAM (fits current budget)
  * 16k context: ~20.89 GB estimated total VRAM (fits current budget)

- Note: vLLM uses paged attention/runtime memory planning; estimates are rough lower bounds.
- trust-remote-code enabled: non-standard architecture (transformers probe unavailable).
- Tool format detected (xml), but no supported vLLM tool parser was selected.
- Model-card serving recommendations read from README.md: {'reasoning_parser': 'nemotron_v3', 'tool_call_parser': 'qwen3_coder'}.
- [2026-08-25] Validated the Nemotron vLLM profile on the RTX 4090: max-model-len=262144, gpu-memory-utilization=0.95, max-num-batched-tokens=8192, max-num-seqs=16, Marlin NVFP4 MoE, FlashInfer Mamba with align cache mode, BF16 KV, prefix caching, generation-config=vllm, nemotron_v3 reasoning parser, qwen3_coder tool parser, automatic tool choice. Native 16-concurrency random benchmark (8,192 input / 128 output, 32 requests) completed 32/32 successfully: 17.23s, 237.79 output tok/s aggregate, P50 TTFT 2.36s, P95 TTFT 6.59s, P50 E2E 8.53s, P95 E2E 12.99s. Use tool_choice=auto; required may repeat calls.
```

- Chat template/tokenizer metadata is read from the model directory unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-vllm` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: nvidia--nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4
```
