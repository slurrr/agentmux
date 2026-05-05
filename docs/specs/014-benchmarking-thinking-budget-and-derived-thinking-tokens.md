# Spec: benchmarking thinking budget and derived thinking tokens

## Problem

The current bench uses one token cap for two different jobs:

- giving the model enough runway to think
- constraining the visible answer for short-format checks

That makes the three concise serving cases harder to interpret than they should be, because the request cap can crowd out the final answer even when the benchmark only wants to test concision.

We also want a per-case signal for how much reasoning runway each model used, but vLLM 0.20.0 does not expose a native `reasoning_tokens` usage field.

## Scope

This spec covers:

- separating request runway from visible-answer limits in the bench
- keeping the three short serving cases as real concision tests
- adding a derived thinking-token field per case
- using only facts that vLLM actually returns plus local token counting of the visible response

It does not cover:

- suppressing thinking in the template
- changing the active Qwen3.5 chat template
- adding new judge logic
- changing workspace/tool behavior beyond the token accounting needed for this split

## Requirements

1. The bench must continue to let the model think normally.
2. The three short serving cases must still enforce concise final answers.
3. The benchmark must not treat total completion budget as the same thing as final-answer budget.
4. Per-case accounting must record:
   - prompt tokens
   - total completion tokens from vLLM
   - visible response tokens counted locally from the final answer text
   - derived thinking tokens
5. The derived thinking token field must be computed from verified data, not from assumptions about the model internals.
6. The final answer text and the reasoning text must stay separate in the result payload.

## Constraints

- vLLM 0.20.0 returns `prompt_tokens`, `completion_tokens`, and `total_tokens` in `usage`.
- vLLM 0.20.0 does not return a native `reasoning_tokens` field.
- The bench should send `thinking_token_budget = 2048` on each request to bound reasoning separately from the visible answer cap.
- The installed bench already captures separate `response` and `thinking` text in the result payload.
- The derived thinking count must use the same tokenizer as the served model or an equivalent local tokenizer path already available in the bench environment.
- Do not change the template to hide or disable thinking just to make the numbers look smaller.

## Proposed shape

For each case, add a token accounting block like:

```json
{
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 456,
    "total_tokens": 579
  },
  "token_accounting": {
    "response_tokens": 42,
    "derived_thinking_tokens": 414,
    "derived_thinking_token_source": "completion_tokens_minus_visible_response_tokens"
  }
}
```

Bench summary output should show a compact thinking section with simple aggregates such as:

- mean derived thinking tokens per case
- mean response tokens per case
- derived thinking tokens for the three short serving prompts

Detailed `bench-show` output should also print one small per-case line like `Thinking Tokens: xxxx` so heavy-thinking cases are easy to spot.

## Acceptance criteria

1. The bench keeps thinking enabled and measures it instead of suppressing it.
2. The three concise serving prompts are judged on visible answer length and format, not on total hidden reasoning runway.
3. The result payload contains a derived thinking-token field per case.
4. The CLI shows an average thinking-token summary after a run and prints per-case thinking tokens in `bench-show`.
5. The derived thinking-token field is computed from vLLM completion usage minus locally counted visible response tokens.
6. No assumption is made that vLLM provides native thinking-token accounting when it does not.

## Open Questions

- Which tokenizer access path should the bench use for counting visible response tokens: the served model tokenizer directly, or an already-loaded local tokenizer helper?
- Should the derived thinking-token field be shown in the default summary, the detailed case view, or both?
- If the visible response is empty, should derived thinking tokens equal total completion tokens by definition or should the bench also record a separate empty-response flag?
