# ADR-003: Execution Persistence — Resolved Config Source and Read Access

## Status

Accepted

## Context

Step 2 turns every LLM call from Step 1 into a persisted `Execution` row (`models.py`), retrievable later via `GET /api/v1/executions/{execution_id}`. Two decisions in that design have real alternatives and are hard to change once other steps (Step 4 cost accounting, Steps 9-13 evaluation runs, Step 24 observability) start depending on what an `Execution` row actually contains and who can read it:

1. `Execution.temperature` and `Execution.max_tokens` must reflect what a call *actually used*, not what the caller *requested* — `ExecutionRequest.temperature`/`max_tokens` are optional (`None` means "use the settings default"). Persisting the raw request would mean many rows show `null` for a NOT NULL column (impossible) or, worse, a misleading half-true value. Where should the resolved value come from?
2. An `Execution` row contains one user's actual input and the model's actual output — not just prompt template text. Prompt read access (`GET /api/v1/prompts/{id}`) is "owner or published." Should execution read access follow the same rule?

## Options Considered

### 1. Source of resolved `temperature`/`max_tokens`

**Option A — Read them back from the OpenAI response object itself (chosen).** The Responses API echoes the generation parameters it actually used (confirmed against a real response: `temperature=0.0, max_output_tokens=300` present on the object alongside `model`). `llm_provider.py` already reads `response.model` for `AdapterResponse.model_name` on this same principle; `response.temperature`/`response.max_output_tokens` extend it to the other two resolved fields.

**Option B — Capture the adapter's own resolution locally.** `open_ai_adapter` already computes `settings.openai_default_temperature if temperature is None else temperature` (and the equivalent for `max_tokens`) inline as call arguments. These could be assigned to local variables first, then reused both for the API call and for populating `AdapterResponse`.

Option B duplicates a second copy of "what does None resolve to" logic that has to stay in sync with whatever the adapter actually sent — Option A instead asks the provider what it actually did, which can't drift out of sync by construction, at the cost of trusting the provider to echo request parameters accurately.

### 2. Who can read an `Execution` row

**Option A — Reuse the prompt's "owner or published" rule.** Simple, consistent with every other endpoint in this router.

**Option B — Owner-of-the-execution only, regardless of the prompt's publish state (chosen).**

Option A has a real leak: if user B executes user A's *published* prompt, the resulting row holds B's input and B's output, but A owns the *prompt*, not the *execution*. Under Option A, A could read B's private input/output just by knowing (or guessing sequentially) the execution id — publishing a prompt was never meant to expose what other people privately send it or get back. Option B checks `Execution.user_id`, the person who actually ran it, not `Prompt.owner_id`.

## Decision

- `AdapterResponse.temperature`/`AdapterResponse.max_tokens` are populated from `response.temperature`/`response.max_output_tokens` (the real API response), not from locally-recomputed defaults.
- `GET /api/v1/executions/{execution_id}` allows only `execution.user_id == current_user.id`. Publish status of the underlying prompt has no bearing on execution read access.

## Why

Both decisions optimize for the same thing: an `Execution` row must be trustworthy as the literal record of what happened, to itself (accurate resolved config) and to who's allowed to see it (scoped to whoever actually generated that input/output, not whoever owns the template it came from).

## Tradeoffs

- Option A (resolved-value sourcing) depends on the Responses API continuing to echo these fields; if a future provider (Step 21) doesn't, the adapter for that provider will need Option B's local-capture approach instead — the two aren't mutually exclusive across providers, just per-adapter.
- Option B (owner-only read) means the prompt owner cannot audit how others are using their published prompt via this endpoint. That's an intentional privacy tradeoff, not an oversight; a future aggregate/anonymized "usage stats for my prompt" view, if ever built, would be a separate, deliberately-designed feature — not a relaxation of this rule.
- Step 2 persists only the success path — a failed `open_ai_adapter` call still propagates to the generic 500 handler and writes no `Execution` row (locked in by `test_execute_failure_does_not_persist_execution`). This is a scope boundary, not a correctness gap: Step 3 (failure taxonomy) is where failed attempts get a defined shape worth persisting.

## Revisit When

- Step 21 adds a second provider — check whether its response object also echoes resolved generation parameters, or whether that adapter needs Option B's local-capture approach.
- Step 3 defines failure taxonomy — decide there whether failed executions get persisted with an error status, and if so, whether the owner-only read rule from this ADR still applies unchanged.
