# Learnings

A running glossary of concepts learned while building PromptOps — for your own later reference. Organized by topic, not by date, so you can look things up. Each entry notes where it actually came up in this project and when you learned it.

---

## Python

### `@lru_cache` (2026-09-12)

A decorator that makes a function remember its own past results. The first time you call a decorated function with a given set of arguments, it runs normally and Python caches the return value. Every later call with the *same* arguments skips re-running the function and just hands back the cached value instantly.

Where it showed up: `get_openai_client()` in [llm_provider.py](../llm_provider.py) and `get_settings()` in [config.py](../config.py). Both are called on every single request, but you don't want to reconstruct an OpenAI client or re-parse environment variables every time — `@lru_cache` means the expensive setup happens once, the first time, and every later call is free.

### Exception chaining with `raise ... from ...` (2026-09-19)

Whenever you raise a new exception from inside an `except` block, Python *always* remembers the exception being handled — that's automatic, and shows up in a traceback as "During handling of the above exception, another exception occurred." `__cause__` is different: it's only set when you write `raise NewException(...) from original_exception` explicitly. Doing so changes the traceback wording to "The above exception was the direct cause of the following exception" (a deliberate translation, not an accidental double-fault), and — more usefully — makes the original exception programmatically readable afterward via `caught.__cause__`, so a logger or debugger can recover the real underlying error even though callers only ever catch your normalized type.

Where it showed up: every `except` clause in `open_ai_adapter` ([llm_provider.py](../llm_provider.py)) that maps a raw OpenAI SDK exception onto the project's own `ProviderError` taxonomy — each one uses `raise ProviderXError(str(exc)) from exc` specifically so the real OpenAI exception stays attached and inspectable.

### `dict.get(key, default)` for safe lookups (2026-09-19)

`dict[key]` raises `KeyError` if the key is missing. `dict.get(key)` returns `None` instead — safer, but `None` can still cause problems if you then try to use it as if it were real data. `dict.get(key, default)` returns `default` instead of `None` when the key is missing, and is ignored entirely (you get the real value) when the key *is* present.

Where it showed up: `http_status_mapping.get(status_category, http_status_mapping["unknown_error"])` in [routers/executions.py](../routers/executions.py) — if a future eighth `ProviderError` subclass is ever added and someone forgets to add its category to this mapping, the lookup degrades to a generic response instead of crashing inside the code that's specifically responsible for handling failures gracefully.

### `try / except / else` (2026-09-19)

Code in an `else` block after `try`/`except` only runs if the `try` block completed with *no* exception at all. The practical reason to use it instead of just writing more code at the end of the `try` block: it keeps the `try` scoped to exactly the operation whose failure you're handling. Code that depends on that operation having succeeded belongs in `else`, not the `try` — otherwise, if the `except` clause is ever broadened later (e.g. someone adds a second, wider `except` for logging), code that should never have been "part of the guarded operation" could suddenly start being caught by it too.

Where it showed up: `execute_llm_provider` in [routers/executions.py](../routers/executions.py) — `try` calls `execute_with_retry`, `except ProviderError` persists a failure row, `else` persists the success row. Building the success `Execution` row is deliberately not inside the `try`.

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

### `server_default` needs a real SQL default, and a new `NOT NULL` column on a populated table needs one (2026-09-19)

`Column(..., nullable=False)` with no `server_default` works fine for a brand-new table, but adding such a column to a table that already has rows fails outright — the database has no value to put in the existing rows and refuses the `ALTER TABLE`. A `server_default` (a real database-level default, not just a Python-level one) fixes this by telling the database what to backfill existing rows with. Separately: for a numeric column, prefer `sa.text("1")` over a bare Python string `"1"` — both actually work (verified directly against Postgres: a bare string renders as `DEFAULT '1'`, which Postgres happily casts to the integer `1`), but `sa.text(...)` is the explicit, dialect-aware way to say "this is raw SQL," matching how this same codebase already does it elsewhere (`Prompt.current_version`) rather than relying on Postgres's implicit string-to-number casting.

Where it showed up: adding `Execution.retry_attempts` (`NOT NULL`, `server_default=sa.text('1')`) to an `executions` table that already had a real row from Step 2's testing — verified the backfill actually landed as `1`, not just that the migration ran.

---

## FastAPI

### Route config lives on the decorator, not the function signature (2026-09-13)

`response_model=` and `status_code=` are arguments to the route decorator (`@router.post(..., response_model=X, status_code=201)`), not to the endpoint function itself. Writing them as function parameters (`def my_route(..., response_model=X)`) doesn't configure anything — FastAPI just tries to treat `response_model` as a request parameter, using whatever you set as its "default value," which breaks the route.

Where it showed up: an early draft of `execute_llm_provider` in [routers/executions.py](../routers/executions.py) had exactly this mix-up.

### An `APIRouter`'s `prefix` must start with `/` (2026-09-13)

`APIRouter(prefix="api/v1/executions")` (no leading slash) fails an internal FastAPI assertion at import time, crashing the whole app on startup — not just that router. `APIRouter(prefix="/api/v1/executions")` is required.

Where it showed up: the same file, while adding the second router for `GET /api/v1/executions/{id}`.

### A dependency can have its own dependency, and either one can short-circuit before your route body ever runs (2026-09-20)

`Depends(...)` chains nest. `get_current_user`'s own signature is `token: str = Depends(oauth2_scheme)` — `oauth2_scheme` is itself a dependency that runs *before* `get_current_user`'s body does, and if it can't find a valid `Authorization` header, it raises its own `401` on the spot, without ever handing control to `get_current_user`. That matters for debugging: a print statement at the very top of `get_current_user` proves nothing if the request never got that far — you have to know a dependency has its own dependency to know where to actually look.

Where it showed up: debugging a `401 "Not authenticated"` on `/execute` via Swagger. The generic message (not the custom `"Could not validate credentials"` that `get_current_user`'s own body raises) plus a silent print statement together confirmed the request was being rejected by `oauth2_scheme` itself — before `get_current_user` ever started — because no token was actually attached to that specific request.

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

---

## AI / LLM Provider Integration

### Provider SDKs often retry internally by default (2026-09-19)

Before assuming your own retry logic is the only thing retrying a failed call, check whether the provider's SDK already retries some failures on its own. The OpenAI Python SDK defaults to `max_retries=2`, silently retrying things like connection errors and 5xx responses before ever raising an exception to your code. If you then add your own retry loop on top without knowing this, "3 attempts" in your own logs or database could actually represent up to 9 real, billed provider calls — a hidden cost multiplier that's invisible unless you go looking for it.

Where it showed up: `OpenAI(..., max_retries=0)` in `get_openai_client()` ([llm_provider.py](../llm_provider.py)), disabling the SDK's own retries so `execute_with_retry`'s bounded loop is the single, observable source of every retry attempt.

### Normalizing provider errors into your own taxonomy (2026-09-19)

A third-party SDK's exception types are an implementation detail of that specific provider — catching them directly throughout your app couples your business logic to that SDK's exact class hierarchy. Instead, map each SDK exception to a small set of your own exception types at the one boundary that talks to the SDK, each carrying the properties your app actually needs to make decisions (here: `retryable: bool`, so a retry loop never needs to know seven different OpenAI class names, and `status_category: str`, so a router can turn any provider failure into the right HTTP response with one dictionary lookup instead of a long `if/elif` chain per exception type).

Where it showed up: `provider_errors.py`'s `ProviderError` hierarchy, populated by `open_ai_adapter`'s `except` chain in [llm_provider.py](../llm_provider.py).

### Exponential backoff with full jitter (2026-09-19)

Retrying a failed call immediately, or after the same fixed delay every time, tends to make things worse under real load — many failed clients all retry at once, hitting the struggling service with a synchronized burst right as it's trying to recover. "Full jitter" backoff fixes this by picking a *random* delay between `0` and a ceiling that grows with each attempt (`min(cap, base * 2^attempt)`), rather than sleeping a fixed or lightly-jittered amount — two clients that failed at the same instant are very unlikely to retry at the same instant.

Where it showed up: `_compute_backoff_delay` in [llm_provider.py](../llm_provider.py), used by `execute_with_retry` between attempts — overridden by the provider's own `Retry-After` header when a `RateLimitError` supplies one, since that's more authoritative than a guess.

### Provider errors often carry structured detail beyond the message string (2026-09-20)

A provider SDK's exception isn't just a string to print — OpenAI's `APIError` exposes `.param` (which specific request field got rejected) and `.code` alongside `.message`, pulled straight from the response body. Reading `exc.param` tells you programmatically *which field* was the problem, without having to parse or pattern-match the human-readable message text.

Where it showed up: diagnosing a real `422` on `/execute` — the persisted `status` (`invalid_request`) said only *that* something about the request was rejected; printing `str(exc)` revealed the underlying `openai.BadRequestError`, whose `param` field was literally `"temperature"` — the specific model being tested doesn't accept that parameter at all. This is also the field a future fix would key off of, rather than pattern-matching the message text.

---

## Debugging Techniques

### Trust the raw error over a coarse category when a generic response isn't enough to diagnose (2026-09-20)

A well-designed error taxonomy (categories, HTTP status codes) is deliberately coarser than the full truth — that's the point, it's meant to give a *caller* a safe, stable, actionable response. But that same coarseness means the category alone can't always tell *you*, the developer, why something actually failed. When a generic failure category isn't enough to understand a real bug, get the raw, unprocessed error text at the exact point it was first caught (a temporary print or log statement placed there, not several layers downstream where it's already been generalized) before guessing at a root cause from the category name alone.

Where it showed up: debugging a `422 "the request was rejected by the model provider"` from `/execute`. The category (`invalid_request`) was consistent with several different real causes (an invalid model name was the first guess, and was wrong) — only printing `str(exc)` at the point `open_ai_adapter` actually catches the OpenAI exception revealed the real, specific cause (`"Unsupported parameter: 'temperature'..."`). Guessing from the category alone would have led to fixing the wrong thing.
