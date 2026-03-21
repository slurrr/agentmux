# 0004: Precedence And Naming Must Be Explicit

## Status
Accepted

## Context
Drift also appeared in two recurring forms:
- silent normalization of names that the user did not ask for
- silent precedence choices between competing stack inputs

Both create avoidable confusion in a repo whose value depends on keeping human stack composition
predictable.

## Decision
Do not silently normalize or reinterpret names.

Examples:
- served model names should remain exactly what the user intends to expose
- stack names are local handles and should not be treated as API-facing canonical names unless specified

Do not silently choose precedence between stack parts when overlap exists.

If two stack inputs attempt to control the same operational flag or behavior, the repo should define the precedence rule explicitly in docs/specs.

Current precedence for launch-relevant overlap:
- defaults args < service args
- defaults assets < service assets
- asset-backed launch fields override same-name raw args

## Consequences
- Agents must not invent lowercased or normalized names “for cleanliness.”
- Overlap between stack domains like `args` and `assets` must be documented and tested.
- Predictability takes priority over clever fallback behavior.
