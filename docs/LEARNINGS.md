# Learnings

A running glossary of concepts learned while building PromptOps — for your own later reference. Organized by topic, not by date, so you can look things up. Each entry notes where it actually came up in this project and when you learned it.

---

## Python

### `@lru_cache` (2026-09-12)

A decorator that makes a function remember its own past results. The first time you call a decorated function with a given set of arguments, it runs normally and Python caches the return value. Every later call with the *same* arguments skips re-running the function and just hands back the cached value instantly.

Where it showed up: `get_openai_client()` in [llm_provider.py](../llm_provider.py) and `get_settings()` in [config.py](../config.py). Both are called on every single request, but you don't want to reconstruct an OpenAI client or re-parse environment variables every time — `@lru_cache` means the expensive setup happens once, the first time, and every later call is free.

---

## SQLAlchemy / ORM

### `relationship()` vs. a `Column` (2026-09-13)

A `Column(..., ForeignKey(...))` is the real database column — it's what's actually stored, what a migration creates, what enforces referential integrity. A `relationship("OtherModel")` is a separate, purely-Python convenience layered on top: it doesn't touch the schema at all, it just tells SQLAlchemy "when someone accesses `my_row.other_thing`, follow the FK column and hand me back the object it points to." You always need the FK column; the `relationship()` is optional sugar for navigating it without writing a query yourself.

Where it showed up: `Execution.user`/`Execution.prompt`/`Execution.prompt_version` in [models.py](../models.py).

### Lazy loading and the N+1 problem (2026-09-13)

By default, touching a `relationship()` attribute (e.g. `execution.prompt_version`) fires a brand-new SQL query the moment you access it — this is called "lazy" loading. For looking at one row, that's harmless (a couple of extra cheap queries). The trap is looping over *many* rows and touching a relationship on each one — that's one query per row on top of the original query, which gets slow fast without any obvious sign in the code. The fix, when you actually build a list endpoint, is `joinedload()` (from `sqlalchemy.orm`), which folds the related data into a single query with a `LEFT OUTER JOIN` instead.

Where it showed up: discussed while designing `Execution`'s relationships, not yet needed since Step 2 only fetches one execution at a time.

### `db.flush()` vs. `db.commit()` (2026-09-13)

`flush()` pushes pending changes (inserts/updates) to the database *within the current open transaction* — the row genuinely exists there and can even be read back (e.g. to get a generated id), but it isn't durable yet. `commit()` is what actually closes out the transaction and makes it permanent. If a session gets closed (`db.close()`) with changes flushed but never committed, they get silently rolled back — it can *look* like it worked (you can read the row back inside the same session) right up until the moment it disappears.

Where it showed up: a real bug in an early draft of `execute_llm_provider` in [routers/executions.py](../routers/executions.py) — it did `add()` → `flush()` → `refresh()` with no `commit()`, so persisted executions would have silently vanished the moment each request ended.

---

## FastAPI

### Route config lives on the decorator, not the function signature (2026-09-13)

`response_model=` and `status_code=` are arguments to the route decorator (`@router.post(..., response_model=X, status_code=201)`), not to the endpoint function itself. Writing them as function parameters (`def my_route(..., response_model=X)`) doesn't configure anything — FastAPI just tries to treat `response_model` as a request parameter, using whatever you set as its "default value," which breaks the route.

Where it showed up: an early draft of `execute_llm_provider` in [routers/executions.py](../routers/executions.py) had exactly this mix-up.

### An `APIRouter`'s `prefix` must start with `/` (2026-09-13)

`APIRouter(prefix="api/v1/executions")` (no leading slash) fails an internal FastAPI assertion at import time, crashing the whole app on startup — not just that router. `APIRouter(prefix="/api/v1/executions")` is required.

Where it showed up: the same file, while adding the second router for `GET /api/v1/executions/{id}`.

---

## Testing

### Fixtures go stale when the interface they mock changes (2026-09-13)

A hand-built test fixture (a `SimpleNamespace` standing in for a real API response, or a helper that constructs a Pydantic model with hardcoded defaults) encodes an assumption about what fields exist at the time it was written. When you later add a required field to the real schema, every fixture built before that change is now incomplete — tests fail not because the new code is wrong, but because the fixture hasn't caught up. The fix is updating the fixture's defaults, not the production code.

Where it showed up: adding `temperature`/`max_tokens` to `AdapterResponse` broke `_fake_openai_response()` in [test_llm_provider.py](../test_llm_provider.py) and `_fake_adapter_result()` in [test_executions.py](../test_executions.py) — both predated the new fields.

---

## Design Patterns

### Persist resolved values, not raw optional request values (2026-09-13)

When a request field is optional and falls back to a default ("use `settings.default_x` if the caller didn't specify"), don't store the caller's raw (possibly-`None`) input in a historical record — store what actually happened. Otherwise your own audit trail can't tell you what config a given call actually used, and a `NOT NULL` column will outright reject a `None`. Where possible, read the resolved value back from the most authoritative source available (e.g. the provider's own response, which echoes back what it actually used) rather than re-implementing the same "resolve this default" logic a second time somewhere else, which can drift out of sync.

Where it showed up: `Execution.temperature`/`Execution.max_tokens` in [routers/executions.py](../routers/executions.py), sourced from `AdapterResponse` (itself reading `response.temperature`/`response.max_output_tokens` off the real OpenAI response in [llm_provider.py](../llm_provider.py)) rather than from `ExecutionRequest`'s optional fields directly. See [ADR-003](decisions/ADR-003-execution-persistence-and-access.md).

### Access control scoped to the actual data owner, not an adjacent owner (2026-09-13)

When one resource (an `Execution`) is created *through* another resource (a `Prompt`) but contains its own private data (a specific user's input/output), read access should be scoped to whoever actually generated that data — not to whoever owns the resource it was created through. Copy-pasting an existing ownership check from a related endpoint can silently create a privacy leak if the two resources don't actually have the same owner in every case.

Where it showed up: `GET /api/v1/executions/{id}` checks `execution.user_id`, deliberately not `prompt.owner_id` — a published prompt can be executed by someone other than its owner, and that executor's input/output shouldn't become readable to the prompt owner just because they own the prompt. See [ADR-003](decisions/ADR-003-execution-persistence-and-access.md).

---

## Tooling

### Alembic: "Target database is not up to date" (2026-09-13)

`alembic revision --autogenerate` refuses to run unless the database's current revision matches the script directory's head revision — it needs to diff against the real current schema to generate an accurate migration, and if a migration file exists that was never applied (`alembic upgrade head` never run), the DB is "behind" the scripts on disk. Check with `alembic current` (what the DB thinks it's at) vs. `alembic heads` (what the latest script file is). If the unapplied migration was never run against the database, deleting that stale file is safe — nothing in the actual DB depends on it.

Where it showed up: hit this directly while regenerating the `executions` table migration after fixing a `nullable` bug in the first draft.

### `time.perf_counter()` for measuring elapsed time (2026-09-13)

A monotonic clock meant specifically for measuring durations, unlike `time.time()` (wall-clock time, which can jump backward from NTP corrections). Read it immediately before and after the thing you're timing, subtract, and only the code in between is measured — anything outside that window (DB queries before or after) leaks into the number if you place the calls loosely.

Where it showed up: measuring `latency_ms` around only the `open_ai_adapter(...)` call in [routers/executions.py](../routers/executions.py), not the surrounding DB lookups or the persistence write.
