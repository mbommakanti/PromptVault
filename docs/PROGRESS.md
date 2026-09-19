# PromptOps Build Progress

Tracks progress through the Atomic Build Guide (Section 7 of `docs/PromptOps_AI_Engineer_Build_Guide.docx`). One entry per completed step: what was done, how it was verified, and the stop condition that justified moving on.

**Current status: Step 3 complete. Not yet started: Step 4.**

---

## Step 0 — Baseline PromptVault ✅ (2026-08-21)

**Goal:** Freeze and understand the current system before adding LLM behavior.

**Done:**
- Full existing test suite verified passing before any changes (21/21), and again after (23/23).
- Fixed `create_prompt` atomicity — it previously committed the `Prompt` row and the initial `PromptVersion` row in two separate transactions, so a failed version insert could leave an orphaned `Prompt`. Now uses a single `flush()` + one `commit()`. Regression test: `test_create_prompt_leaves_no_orphan_when_version_insert_fails` (`test_prompts.py`) — forces a real `IntegrityError` via a colliding unique-constraint row, not a mock; verified to fail against the pre-fix code and pass against the fix.
- Fixed `update_prompt`'s version-increment race condition — it previously computed the next `version_number` in Python from an already-loaded `current_version` (a read-modify-write race under concurrent edits). Replaced with a single atomic `UPDATE prompts SET current_version = current_version + 1 ... RETURNING current_version` statement, portable across SQLite (test) and Postgres (prod). Regression test: `test_content_update_version_bump_ignores_stale_cached_reads` — calls the real endpoint function directly with two sessions holding stale reads, exploiting SQLAlchemy's identity-map behavior to genuinely reproduce staleness; verified to fail against the pre-fix code and pass against the fix.
- Reviewed and raised the prompt-size policy: `PromptCreate`/`PromptUpdate` `content` max length was an untuned placeholder (1000 chars, ~250 tokens). Raised to 20,000 chars as a deliberate, documented sanity ceiling on stored template text — see [ADR-001](decisions/ADR-001-prompt-size-policy.md).
- Verified `/api/v1` documentation drift: confirmed the 10 routes actually defined in `routers/prompts.py` and `routers/users.py` match the README's endpoint table exactly. No drift found.
- Confirmed README's existing data-model documentation (`User`, `Prompt`, `PromptVersion`) is accurate and needs no changes.

**Shipped as:**
- PR #1 — atomicity fix, version-increment fix, size-policy change, regression tests.
- PR #2 — `CLAUDE.md` and `docs/` (this file, ADRs, incident journal scaffolding).

**Stop condition:** Able to explain the `User → Prompt → PromptVersion` data flow, the ownership/soft-delete/publish rules, and both concurrency fixes from memory, without assistance.

---

## Step 1 — First real LLM execution ✅ (2026-09-12)

**Goal:** Make one saved prompt version call one model through one provider.

**Done:**
- Added typed provider settings (`config.py`): `ProviderSettings(BaseSettings)` with `openai_api_key` as `SecretStr`, plus `openai_default_model`/`openai_default_temperature`/`openai_default_max_tokens`/`openai_timeout_seconds`, loaded via a `functools.lru_cache`-wrapped `get_settings()` accessor.
- Built a provider adapter (`llm_provider.py`) around OpenAI's **Responses API** (`client.responses.create`, called with `store=False` deliberately — see [ADR-002](decisions/ADR-002-llm-provider-integration.md)). The adapter is a single keyword-only function, `open_ai_adapter(*, input, instructions, model=None, temperature=None, max_tokens=None, timeout=None)`; unspecified values fall back to settings defaults, resolved fresh on every call (not frozen at import time).
- Added a normalized response type, `AdapterResponse` (`schemas.py`): `model_response`, `model_name`, `response_status`, `input_tokens`, `output_tokens`, `total_tokens`, `incomplete_reason`, `response_id`. No OpenAI SDK object is returned or read outside the adapter.
- Added `ExecutionRequest` (`schemas.py`) with bounds on `input` (5-2000 chars), `temperature` (0-2), and `max_tokens` (16-1000) — the same size-policy discipline as [ADR-001](decisions/ADR-001-prompt-size-policy.md), applied to a field that now drives a paid API call.
- Added `POST /api/v1/prompts/{prompt_id}/versions/{version_number}/execute` (`routers/executions.py`). Reuses the existing owner-or-published/soft-delete lookup rule verbatim. Maps stored `PromptVersion.content` → `instructions` and the request body's `input` → `input` (see ADR-002 for why). Deliberately does not persist anything (Step 2) and does not catch provider errors (Step 3) — failures currently propagate to the existing generic 500 handler.
- Verified manually end-to-end (real, billed calls) via CLI and Postman: correct field mapping for both a completed response and a truncated (`incomplete`, `incomplete_reason="max_output_tokens"`) response. Also observed directly that a high `temperature` produces provider-`"completed"`-or-`"incomplete"` responses that are nonetheless incoherent — confirming that provider-level status says nothing about output quality, which is the gap the evaluation steps (9-16) exist to close.
- Added regression tests, all mocking the OpenAI client (no real network calls or cost in CI): `test_llm_provider.py` (adapter field-mapping for completed/truncated responses, settings-default fallback, caller overrides, keyword-only-argument guard) and `test_executions.py` (happy path incl. content→instructions mapping, 401/403/404/422 cases).
- Fixed a CI gap: `.github/workflows/ci.yml` had no `OPENAI_API_KEY`, which would have broken CI the moment `get_settings()` became required at import time; added a placeholder value alongside the existing dummy-value pattern.
- Full suite green: 35/35 tests passing, 97% coverage; `ruff check .` clean.

**Shipped as:** not yet committed/pushed — working tree has these changes staged for a commit.

**Stop condition:** Able to explain exactly what happens from API request to model response — request anatomy (instructions/input roles, generation parameters), response anatomy (status vs. `incomplete_details`, token usage, provider response ID) — without assistance.

---

## Step 2 — Execution persistence ✅ (2026-09-13)

**Goal:** Turn every model call into an inspectable historical execution.

**Done:**
- Added the `Execution` model (`models.py`): FK columns to `User`/`Prompt`/`PromptVersion` (all `nullable=False`, indexed on `user_id`/`prompt_id`), resolved `model_name`/`temperature`/`max_tokens`, `input`/`output`, `status`/`incomplete_reason`, token counts, `provider_response_id`, `latency_ms`, and a `server_default=func.now()` `created_at` — matching the immutability/append-only-fact-record convention, not the editable-entity convention `Prompt` uses. Plain (non-`back_populates`) `relationship()`s to `User`/`Prompt`/`PromptVersion` for read convenience.
- Migration `ac5e642162ec_create_executions_table.py`, applied to the local dev DB and verified against the actual Postgres schema.
- Added `ExecutionOut` (`schemas.py`), matching the model's nullability exactly (only `incomplete_reason` is optional).
- Extended `AdapterResponse` (`schemas.py`) with required `temperature`/`max_tokens`, and `open_ai_adapter` (`llm_provider.py`) to populate them by reading `response.temperature`/`response.max_output_tokens` back from the real OpenAI response object — confirmed against a real response that these fields exist and reflect the actually-used values, not by trusting the assumption blind. See [ADR-003](decisions/ADR-003-execution-persistence-and-access.md) for why this was chosen over locally recomputing the same defaulting logic a second time.
- `execute_llm_provider` (`routers/executions.py`) now times only the `open_ai_adapter(...)` call (`time.perf_counter()`), builds an `Execution` row from the *resolved* adapter-response values (not the raw, possibly-`None` request values), persists it (`add`/`commit`/`refresh`), and returns `ExecutionOut` with `201 Created`. Only the success path persists — a raised provider error still propagates to the generic 500 handler and writes no row (Step 3's job to change).
- Added `GET /api/v1/executions/{execution_id}` on a new `execution_router` (`/api/v1/executions` prefix, registered separately in `main.py`). Access is **owner-of-the-execution only** (`execution.user_id == current_user.id`), deliberately stricter than the prompts' "owner or published" rule — see ADR-003 for the privacy reasoning (a published prompt's other executors' input/output must not become readable to the prompt owner).
- Raised `config.py`'s `openai_default_max_tokens` from 300 to 10000, matching `ExecutionRequest.max_tokens`'s existing `le=10000` request-time ceiling (previously the default was well under what a client could explicitly request).
- Tests: 6 new cases in `test_executions.py` (owner GET round-trip, 401, 404, 403-for-prompt-owner-who-isn't-the-executor, and a regression lock on "failure does not persist a row"); updated stale mocks in `test_llm_provider.py`/`test_executions.py` to include the two new `AdapterResponse` fields; updated two tests whose expectations were still `200`/old field names after the endpoint's response shape and status code changed.
- Full suite green: 40/40 passing, 97% coverage.
- Verified manually end-to-end with a real billed call (a code-review-style prompt): persisted row's resolved `temperature`/`max_tokens`, token usage, `latency_ms`, and real `provider_response_id` all correct; retrieved the same execution back via `GET /api/v1/executions/{id}` and reconstructed exactly what ran from the row alone.

**Shipped as:** not yet committed/pushed — working tree has these changes.

**Stop condition:** Able to explain, without assistance: why resolved (not raw-request) config is persisted and where those resolved values come from; why execution read access is scoped to the executor rather than the prompt owner, including the specific leak scenario that rule prevents; and why failure persistence was deliberately deferred to Step 3 rather than solved ad hoc here.

---

## Step 3 — Failure taxonomy and retries ✅ (2026-09-19)

**Goal:** Handle LLM-provider failures intentionally instead of treating everything as "500."

**Done:**
- Added a small internal exception taxonomy (`provider_errors.py`): `ProviderError` base plus six subclasses (`ProviderTimeoutError`, `ProviderConnectionError`, `ProviderRateLimitError`, `ProviderAuthenticationError`, `ProviderServerError`, `ProviderInvalidRequestError`), each carrying a `retryable: bool` and a `status_category: str` class attribute. `ProviderRateLimitError` additionally carries `retry_after: float | None`. This is the same normalization principle already applied to successful responses (`AdapterResponse`) — the OpenAI SDK's own exception types never cross the adapter boundary.
- `open_ai_adapter` (`llm_provider.py`) now wraps its single `client.responses.create(...)` call in an ordered `except` chain (most-specific-first: `APITimeoutError` → `APIConnectionError` → `RateLimitError` → `AuthenticationError` → `InternalServerError` → `APIStatusError` → `APIError`), mapping each real OpenAI exception to the matching normalized type via `raise Normalized(str(exc)) from exc` — preserving both the real message and explicit exception chaining (`__cause__`). `RateLimitError`'s `Retry-After` header is parsed defensively into `retry_after` (missing or non-numeric header degrades to `None` rather than crashing the handler itself).
- Discovered the OpenAI SDK retries certain failures internally by default (`max_retries=2`, confirmed in `_constants.py`) before ever raising to the adapter. Disabled it (`OpenAI(..., max_retries=0)` in `get_openai_client()`) so the app's own retry policy is the single, observable source of retry attempts — otherwise a configured "3 attempts" could have silently meant up to 9 real provider calls.
- Added `execute_with_retry` (`llm_provider.py`): a bounded retry loop wrapping `open_ai_adapter`, retrying only when `exc.retryable`, using full-jitter exponential backoff (`_compute_backoff_delay`, a pure function: `random.uniform(0, min(cap, base * 2**(attempt-1)))`) or the provider's own `Retry-After` value when present (capped at `retry_backoff_max_seconds` either way, since the router runs synchronously in a thread-pool worker and shouldn't block on an unbounded provider-requested wait). Sets `.attempts` on the exception before the final re-raise once the bound is exhausted; returns `(AdapterResponse, attempts)` on success. New settings in `config.py`: `openai_retry_max_attempts` (3), `openai_retry_backoff_base_seconds` (1.0), `openai_retry_backoff_max_seconds` (20.0).
- Extracted `resolve_execution_config(model, max_tokens, temperature)` (`llm_provider.py`) as a shared pure function — used by `open_ai_adapter` for the real call and by the router's failure path, so "what model/temperature/max_tokens were we attempting" doesn't get duplicated and drift between the two.
- Migration `41a7ef227a90`: `Execution.output`/`input_tokens`/`output_tokens`/`total_tokens`/`provider_response_id` are now nullable (genuinely unknowable when a call never gets a response — deliberately not defaulted to `0`, which would corrupt future cost/usage aggregates). `model_name`/`temperature`/`max_tokens`/`status` stay `NOT NULL`, populated from `resolve_execution_config` even on failure since that's echoing the attempted request, not fabricating provider behavior. New `retry_attempts` column (`NOT NULL`, `server_default=sa.text('1')`) — verified directly against the live Postgres schema (not just the migration file) that the one pre-existing Step 2 row backfilled correctly to `1`.
- `routers/executions.py`'s `execute_llm_provider` restructured into `try / except ProviderError as exc / else`: the `except` branch builds and persists a failure `Execution` row (`status=exc.status_category`, `retry_attempts=exc.attempts`, resolved config, all success-only fields `None`) via a shared `build_execution_object(*, ...)` keyword-only helper (also used by the success path), then raises an `HTTPException` via a module-level `status_category -> (http_status, generic_detail_message)` mapping, looked up defensively (`.get(status_category, http_status_mapping["unknown_error"])`) so an unmapped future category degrades to a generic 502 instead of crashing the error-handling path itself. Failure-path messages are deliberately generic and never echo raw provider text — the `auth_error` category in particular never hints at credentials. `latency_ms` is measured around the whole `execute_with_retry` call (including backoff sleep time), not just the provider round-trip, since that's what the API caller actually waited through.
- Resolves the open question from [ADR-003](decisions/ADR-003-execution-persistence-and-access.md)'s "Revisit When": execution read access stays owner-only (`execution.user_id`) — a failure row is still just an `Execution` row, no new access path was introduced.
- Fixed `test_executions.py`, which broke when `open_ai_adapter` stopped being imported directly into `routers/executions.py` (all `patch("routers.executions.open_ai_adapter", ...)` repointed to `patch("llm_provider.open_ai_adapter", ...)`, since `execute_with_retry` resolves that name from `llm_provider`'s own module namespace). Reworded the now-stale `test_execute_failure_does_not_persist_execution` (renamed to `test_execute_unexpected_non_provider_error_does_not_persist_execution`) to clarify it locks in permanent behavior for non-`ProviderError` exceptions specifically, not a Step 2 gap. Added 4 new tests: terminal failure persists + fails fast (exactly 1 attempt), retryable failure exhausts at exactly `retry_max_attempts` then persists, a success that needed one retry persists the real attempt count (regression lock — `execute_with_retry`'s tuple return was briefly unpacked incorrectly during development), and a failure row resolves `max_tokens`/`temperature` into their correct columns without swapping them (regression lock for a real bug caught during review).
- Full suite green: 44/44 passing, 95% overall coverage (`ruff check` clean on the touched files).
- **Not yet done:** `execute_with_retry`, `_compute_backoff_delay`, and `resolve_execution_config` don't have dedicated unit tests of their own in `test_llm_provider.py` the way `open_ai_adapter` does — their behavior (retry bounding, backoff math, `Retry-After` handling, config resolution) was verified extensively via ad hoc scripts during code review and is exercised indirectly through `test_executions.py`'s router-level failure tests, but isn't locked in as permanent regression coverage at the unit level yet. `llm_provider.py`'s own file coverage is 61%, notably lower than the rest of the codebase, reflecting this gap.

**Shipped as:** not yet committed/pushed — working tree has these changes.

**Stop condition:** Able to explain, without assistance: why retry policy lives in a wrapper around `open_ai_adapter` rather than inside it; why the OpenAI SDK's own default retries had to be explicitly disabled; why terminal errors (auth, invalid request) never enter the backoff path; why a failed execution is still persisted with resolved (not raw-request) config even though no provider response ever came back; and why the HTTP status mapping deliberately never echoes raw provider error text to the caller.

---

## Step 4 — Token and cost accounting (not started)

**Goal:** Make AI cost an observable engineering metric.

Not yet started.
