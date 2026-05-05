# Session: Pi System Prompt Injection

## Test: `./agentmux bench-tools --suite quality --release`

## Changes
- Quality max_tokens cap: `2048`
- All 12 quality cases now have Pi system prompt (enforces conciseness, correct tool use)

## Expected Result
- Mean thinking tokens drop below 512
- Empty responses should drop (system prompt guides model to finish)
- Quality score should improve

## Resume Instruction
Run `./agentmux bench-tools --suite quality --release` and check:
1. Mean thinking tokens (should be <512)
2. Empty evasive/degenerate rate (should drop below 10%)
3. Quality score (should be >0.8)
