# PromptOps Build Progress

Tracks progress through the Atomic Build Guide (Section 7 of `docs/PromptOps_AI_Engineer_Build_Guide.docx`). One entry per completed step: what was done, how it was verified, and the stop condition that justified moving on.

**Current status: Step 0 complete. Not yet started: Step 1.**

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

## Step 1 — First real LLM execution (not started)

**Goal:** Make one saved prompt call one model through one provider.

Not yet started.
