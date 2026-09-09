# ADR-001: Prompt Content Size Policy

## Status

Accepted

## Context

`PromptVersion.content` (the stored, versioned prompt text) was validated in `schemas.py` with `max_length=1000` characters on both `PromptCreate` and `PromptUpdate`. This was an untuned placeholder from Month 1, not a deliberate decision — it was never revisited once the schema was written.

1000 characters is roughly 200-250 tokens (English text averages ~4 characters/token). That's barely enough for a short paragraph, and too small for a realistic system prompt once few-shot examples (build guide Step 6) or structured-output instructions (Step 7) are added. Left alone, this limit would likely become an accidental hard blocker partway through the project, for reasons unrelated to the actual constraint that matters (model context windows and token cost).

It's also important to be precise about what this field does and doesn't govern. `PromptVersion.content` is the raw *template* a user writes and versions — it is not the *rendered* prompt (after variable substitution, arriving in Step 5), and not the *full request* sent to a provider (rendered prompt + few-shot examples + structured-output instructions + system/role messages, which depends on the specific model's context window). A character limit on this one field can only ever be a rough proxy for stored-template size, never a substitute for real per-request token accounting.

A decision was needed on: what limit is actually defensible right now, and how to avoid conflating "sanity check on stored text" with "enforcement of provider token/context-window limits" — a distinction that matters once `ModelConfiguration`, provider adapters, and token accounting exist (Steps 1 and 4).

## Options Considered

### Option 1 — Leave the limit at 1000 characters

Pros:
- No change needed.

Cons:
- Too small for a real system prompt plus even a couple of few-shot examples.
- Would almost certainly need revisiting mid-project, at an inconvenient time, once prompt engineering (Step 6) actually starts.
- The number was never chosen deliberately in the first place, so keeping it doesn't actually resolve anything.

### Option 2 — Remove the length limit entirely

Pros:
- Never blocks legitimate prompt content, however long.

Cons:
- Removes the only sanity/DoS-style guard on this field at the API boundary, conflicting with the project's own security principle of validating at system boundaries.
- Not actually necessary — the real problem is that 1000 is too small, not that a bound shouldn't exist at all.

### Option 3 — Raise to a generous, bounded ceiling as a sanity guard only (chosen)

Pros:
- 20,000 characters (~5,000 tokens) comfortably covers a system prompt plus several few-shot examples for the support-triage benchmark task, without being unbounded.
- Still rejects clearly pathological input (e.g., an entire document pasted into a prompt template).
- Requires no new infrastructure — stays a plain Pydantic `Field(max_length=...)`, since `ModelConfiguration` and per-model token limits don't exist until Step 1/4.
- Keeps the scope of what this field enforces explicit: stored-template size only, not token/cost/context-window enforcement.

Cons:
- Still a characters-not-tokens proxy — imprecise by construction.
- Does not protect against context-window overruns once variables are rendered in (Step 5) or few-shot/structured-output content is appended (Steps 6-7); those need their own enforcement, closer to execution time.

## Decision

Raise `content`'s `max_length` on both `PromptCreate` and `PromptUpdate` (`schemas.py`) from `1000` to `20000` characters. `min_length=5` is unchanged.

## Why

This is the right-sized decision for where the project actually is: it fixes the immediate problem (a too-small, undocumented placeholder) without building token-aware, per-model infrastructure the project doesn't have a use for yet. Per the project's own scope-discipline rule, a `ModelConfiguration`-driven, tokenizer-based limit should wait until there's a concrete model/provider to enforce it against.

## Tradeoffs

We're accepting a rough, non-authoritative character-based ceiling on stored templates now, with the explicit understanding that it will be superseded — not replaced in place, but supplemented — by real token-based enforcement once execution exists. This field does not and will not protect against a rendered prompt or full provider request exceeding a specific model's context window; that enforcement belongs at execution time, against real tokenizer counts.

## Revisit When

- Step 1 introduces the provider adapter and `ModelConfiguration` (model-specific context window becomes known).
- Step 4 introduces real tokenizer-based token/cost accounting.

At that point, decide whether this raw character cap on stored `PromptVersion.content` should be lowered, left as a coarse defense-in-depth check alongside real token-based validation, or removed in favor of enforcement that happens entirely at render/execution time.
