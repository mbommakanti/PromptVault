# ADR-004: LLM Failure Taxonomy, Retry Policy, and Failure Persistence

## Status

Accepted

## Context

Through Step 2, `execute_llm_provider` (`routers/executions.py`) had no `try/except` around the provider call at all — any failure (a timeout, a rate limit, a bad API key, an invalid model name) fell straight through to the generic `Exception` handler in `main.py`, returning a flat, undifferentiated `500` and writing no `Execution` row. This was a deliberate scope boundary at the time (see [ADR-003](ADR-003-execution-persistence-and-access.md)'s "Revisit When"), not an oversight — Step 2's job was proving success-path persistence first.

Several real, interlocking decisions had to be made to close that gap intentionally:

1. Provider failures come in categories with genuinely different correct responses — a `401` (bad key) will never succeed no matter how many times it's retried; a `429` (rate limited) or a transient `5xx` plausibly will. Treating every failure identically (either "never retry" or "always retry") is wrong in one direction or the other.
2. Once a retry loop exists, it needs a hard bound. Unbounded or blind retries directly risk unnecessary duplicate billed provider calls.
3. The `Execution` table's columns (`output`, token counts, `provider_response_id`) were all `NOT NULL`, populated only from a successful response — there was no shape for a row representing a call that never got one.
4. Whatever comes back to the API's own caller has to be a deliberate HTTP contract, not a leak of internal exception types or raw provider error text (the latter risks exposing operational details, e.g. hinting that a request was rejected for auth reasons).

## Options Considered

### 1. Where does error normalization live, and how much detail does it carry?

**Option A — Catch and normalize at the adapter boundary, with a `retryable` flag and a `status_category` string per exception type (chosen).** `open_ai_adapter` maps each real OpenAI SDK exception (`APITimeoutError`, `APIConnectionError`, `RateLimitError`, `AuthenticationError`, `InternalServerError`, and the remaining `APIStatusError` subtypes bucketed together) onto one of six internal `ProviderError` subclasses plus the bare base as an unmapped fallback. Each carries `retryable: bool` and `status_category: str` as class attributes.

**Option B — Let SDK exceptions propagate and branch on them wherever they're handled.** Simpler up front, but couples the router (and anything else that might need to react to a provider failure later) directly to the OpenAI SDK's exact exception hierarchy — the same "provider SDK objects should not leak" problem `AdapterResponse` already solves for successful responses, just unaddressed for the failure path.

Option B would also make retry-eligibility a scattered, per-call-site judgment instead of a property the exception itself carries.

### 2. Where does retry logic live, and what policy?

**Option A — A separate bounded-retry wrapper (`execute_with_retry`) around the single-call adapter, using full-jitter exponential backoff, retrying only when `exc.retryable` (chosen).** `open_ai_adapter` stays "one call in, one call out (or one exception out)" — unchanged in shape from Steps 1-2, still trivially mockable in isolation. `execute_with_retry` owns the loop, the backoff math (`_compute_backoff_delay`, a pure function), attempt counting, and preferring a `RateLimitError`'s own `Retry-After` value (capped at a configured maximum) over a computed guess when the provider supplies one.

**Option B — Retry logic inside `open_ai_adapter` itself.** Would have broken the "one call in, one call out" contract every existing `test_llm_provider.py` test depends on, forcing every adapter-level test to also account for retries.

A related, initially invisible problem surfaced while implementing Option A: the OpenAI SDK retries some failures internally by default (`max_retries=2`, confirmed in the installed SDK's `_constants.py`) *before* ever raising to the adapter. Left unaddressed, this would silently stack with the app's own retry loop — a configured "3 attempts" could mean up to 9 real billed calls. Resolved by passing `max_retries=0` to the `OpenAI(...)` client, making the app's own bounded loop the sole source of retries.

### 3. What does a failure `Execution` row look like?

**Option A — Make only the fields that are genuinely unknowable nullable (`output`, `input_tokens`, `output_tokens`, `total_tokens`, `provider_response_id`); keep `model_name`/`temperature`/`max_tokens`/`status` `NOT NULL`, populated from what was requested (or its default) even on failure (chosen).**

**Option B — Make the resolved-config fields nullable too, since a failure never got a real provider-echoed value for them.**

Option B is honest in the strict sense ("we don't know what the provider would have used"), but loses real, queryable value for no benefit — unlike token counts (which only the provider can report, and which a `0` would misrepresent for cost accounting), `model_name`/`temperature`/`max_tokens` are known *before* the call is even attempted; the same trivial defaulting logic (`resolve_execution_config`, extracted specifically so this wouldn't have to be duplicated between the adapter and the router) already knows the answer. A failure row with `model_name = "gpt-4o-mini"` supports "show me every failed execution against this model," which a `NULL` cannot.

### 4. What HTTP response does the API's own caller see?

**Option A — A `status_category -> (http_status, generic_message)` mapping, deliberately never echoing raw provider text, especially not for `auth_error` (chosen).** `timeout`→504, `connection_error`/`rate_limited`/`auth_error`→503, `provider_error`→502, `invalid_request`→422 (the one category plausibly caused by the caller's own input — an unvalidated `model` field), unmapped/`unknown_error`→502.

**Option B — Pass through the provider's own status code and/or message.** Rejected: an OpenAI-side `401` reflects a misconfigured server-side API key, not a fault of the API's own caller, and surfacing that distinction (or any raw provider message) risks leaking operational detail about the service's own credentials.

## Decision

- `provider_errors.py` defines `ProviderError` and six subclasses, each with `retryable` and `status_category`; `ProviderRateLimitError` additionally carries `retry_after: float | None`, read from OpenAI's `Retry-After` header when present.
- `open_ai_adapter` maps every OpenAI SDK exception to one of these via `raise Normalized(str(exc)) from exc`, preserving both the real message and explicit exception chaining.
- `execute_with_retry` wraps `open_ai_adapter` with a bounded, full-jitter backoff loop, retrying only `retryable` failures, preferring `retry_after` (capped) over computed backoff, and setting `.attempts` on the exception before its final re-raise once exhausted. The OpenAI client is constructed with `max_retries=0` so this loop is the only source of retries.
- `Execution.output`/`input_tokens`/`output_tokens`/`total_tokens`/`provider_response_id` are nullable; `model_name`/`temperature`/`max_tokens`/`status` stay `NOT NULL`. A new `retry_attempts` column (`NOT NULL`, backfilled to `1` for all pre-Step-3 rows via `server_default`) records how many attempts an execution — success or failure — actually took.
- `routers/executions.py` maps `status_category` to an HTTP status and a generic, provider-detail-free message before responding, while still persisting the full category and attempt count in the row itself for anyone with legitimate read access to that execution.

## Why

Every one of these decisions optimizes for the same thing ADR-003 already established for successful executions: a stored `Execution` row — success or failure — should be a trustworthy, literal record of what was actually attempted and what actually happened, and the API's external contract should never leak more about *why* something failed than the caller needs to know.

## Tradeoffs

- The `invalid_request` → `422` mapping assumes the cause is plausibly the caller's own `model` field (still unvalidated free text in `ExecutionRequest`), but genuinely can't distinguish that from other 4xx-shaped provider rejections bucketed under the same category. Worth revisiting if this proves misleading in practice.
- Bucketing `PermissionDeniedError`/`NotFoundError`/`ConflictError`/`UnprocessableEntityError` all under the single `invalid_request` category (rather than giving each its own `ProviderError` subclass) is a deliberate simplification for a single-provider project with one fixed request shape — a wider surface of distinct provider request types would likely justify splitting these out later.
- The `status_category -> HTTP status` mapping intentionally lives in `routers/executions.py`, not on the `ProviderError` classes themselves — keeping "what failed" (provider-agnostic) separate from "what does *this* API return for it" (a transport-layer decision). If a second entry point ever exposes execution failures differently, it would define its own mapping rather than share this one.
- `execute_with_retry`'s own retry-bounding, backoff math, and config-resolution logic are verified so far only via ad hoc scripts during code review and indirectly through router-level tests (`test_executions.py`) — not yet locked in with dedicated unit tests in `test_llm_provider.py` the way `open_ai_adapter` is. Flagged in `docs/PROGRESS.md` as unfinished, not silently dropped.

## Revisit When

- A second LLM provider is added (Step 21) — its adapter will need its own SDK-exception-to-`ProviderError` mapping; the taxonomy itself, being provider-agnostic, shouldn't need to change.
- `ExecutionRequest.model` gains real validation against a known model list — at that point, reconsider whether `invalid_request` still deserves a blanket `422`, or whether a validated model field shifts more of that category toward "this is actually our bug, not the caller's."
- Dedicated unit tests for `execute_with_retry`/`_compute_backoff_delay`/`resolve_execution_config` are added to `test_llm_provider.py` — until then, this ADR's retry-policy claims rest partly on manual verification rather than permanent regression coverage.

## Update (2026-09-20): the external-message decision had an internal cost

Manually testing the `/execute` endpoint against a model that rejects the `temperature` parameter surfaced a real consequence of the "never echo raw provider text externally" decision above: it also meant *nobody* — not just the external caller — could see why an `invalid_request` failure actually happened, beyond its bare category. The only way to find the real reason was a temporary `print(str(exc))`.

**Resolved:** added `Execution.error_message` (`Text`, nullable), populated with `str(exc)` on the failure path and `None` on success. Deliberately **not** added to `ExecutionOut` — it's stored and inspectable (direct query, or a future internal-only view) but never serialized through either the execute endpoint's own response or `GET /api/v1/executions/{id}`. This doesn't reopen the original decision; it separates two things that were previously conflated by omission: *what the API's caller is told* (still generic, still safe) and *what the system itself remembers* (now the real provider text, for whoever has legitimate access to the row).

Still open, not yet decided: `open_ai_adapter` sends `temperature` unconditionally regardless of whether the target model supports it. Two shapes were discussed — a maintained "no-temperature" model list, or reactively detecting `exc.param == "temperature"` on a `BadRequestError` and retrying once with a corrected request (a bounded repair, not a reliability retry — the request itself must change, not just be re-sent). No decision made; tracked in `docs/PROGRESS.md`.
