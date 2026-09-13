# PromptOps Build Progress

Tracks progress through the Atomic Build Guide (Section 7 of `docs/PromptOps_AI_Engineer_Build_Guide.docx`). One entry per completed step: what was done, how it was verified, and the stop condition that justified moving on.

**Current status: Step 1 complete. Not yet started: Step 2.**

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

## Step 2 — Execution persistence (not started)

**Goal:** Turn every model call into an inspectable historical execution.

Not yet started.
