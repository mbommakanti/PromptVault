# PromptVault → PromptOps

A FastAPI backend for storing, versioning, and executing LLM prompts — with JWT authentication, ownership-based access control, and observable LLM execution (token usage, cost, latency, retries, and failure categories persisted for every call).

PromptVault is being evolved incrementally into **PromptOps**, an evaluation-first LLM engineering platform: the goal is to answer *"why is this prompt/model configuration the one we should ship?"* with measured evidence rather than manual eyeballing.

**Live demo:** [promptops-api.bommakantimaneesh.dev/docs](https://promptops-api.bommakantimaneesh.dev/docs)

> Hosted on a free tier — the first request after a period of inactivity can take ~30–60s while the service wakes up.

## Overview

PromptVault solves a common problem for anyone working seriously with LLMs: prompts end up scattered across notes apps, Slack messages, and code comments, with no single place to store them, track how they've evolved, or control who can see what.

PromptVault provides a backend service where users can create, update, and organize prompts, with every content change automatically preserved as a new version — nothing is ever silently overwritten. Prompts can be kept private or published for other users to view.

## Features

- **JWT authentication** — signup and login with hashed passwords (bcrypt) and signed access tokens
- **Ownership-based access control** — users can only modify their own prompts; published prompts are readable by anyone
- **Automatic prompt versioning** — every content update creates a new version rather than overwriting history
- **Soft deletes** — deleted prompts are preserved (not destroyed) and excluded from normal queries
- **Publish/unpublish toggle** — control whether a prompt is private or shared
- **API versioning** — all routes live under `/api/v1`, so future breaking changes can ship under `/api/v2` without disrupting existing clients
- **Rate limiting** — login, signup, and LLM execution are limited to 5 requests/minute per IP, reducing brute-force/spam risk and capping how fast anyone can spend provider credits
- **Structured error responses** — a global exception handler returns a consistent JSON error shape across the whole API, including rate-limit (429) responses
- **LLM execution** — run a saved, immutable prompt version against OpenAI through a normalized provider adapter; returns generated text, completion status, token usage, and the provider's response ID
- **Execution history** — every execution is persisted as an inspectable, immutable record (resolved model config, input, output, token usage, latency, provider response ID, retry attempts) and retrievable by id, scoped to whoever ran it
- **Provider failure handling with bounded retries** — timeouts, connection errors, rate limits, auth failures, and provider 5xx/4xx responses are normalized into an internal taxonomy; transient failures get bounded, jittered exponential backoff (honoring the provider's own `Retry-After` when given), terminal failures fail fast, and every attempt — success or exhausted failure — is persisted with its real attempt count
- **Token and cost accounting** — every execution records its estimated cost in USD, computed from real provider-reported token usage against a static per-model pricing table, stored as an exact decimal (never a float)
- **Automated test suite** — 55 pytest tests covering auth, ownership, versioning, soft-delete, LLM execution/persistence, provider failure/retry behavior, and cost calculation (provider calls mocked), run against an isolated in-memory database

## Tech Stack

- **FastAPI** — web framework
- **SQLAlchemy** — ORM
- **Alembic** — database migrations
- **Pydantic** — request/response validation
- **PostgreSQL** — database (production, via Neon)
- **python-jose** — JWT encoding/decoding
- **passlib (bcrypt)** — password hashing
- **slowapi** — rate limiting
- **openai** — LLM provider SDK (Responses API)
- **pydantic-settings** — typed, validated provider configuration from environment variables
- **pytest** — automated testing (55 tests, 95% coverage)
- **Docker** — containerized deployment
- **Render** — hosting (Docker web service)
- **Neon** — managed serverless PostgreSQL
- **Cloudflare** — DNS for the custom domain

## Project Structure

```
PromptVault/
├── main.py              # FastAPI app instance, router registration, global exception handlers
├── database.py           # DB engine, session, and dependency
├── models.py              # SQLAlchemy ORM models (User, Prompt, PromptVersion, Execution)
├── schemas.py              # Pydantic request/response schemas
├── auth.py                  # Password hashing, JWT creation/verification, get_current_user
├── rate_limit.py             # Shared slowapi Limiter instance
├── config.py                  # Typed provider settings (ProviderSettings, get_settings)
├── llm_provider.py             # OpenAI provider adapter, bounded retry loop (open_ai_adapter, execute_with_retry)
├── provider_errors.py           # Internal provider-failure taxonomy (ProviderError and subclasses)
├── pricing.py                    # Static per-model pricing table and cost calculation (calculate_cost)
├── routers/
│   ├── users.py               # Signup, login endpoints
│   ├── prompts.py              # Prompt CRUD and versioning endpoints
│   └── executions.py            # LLM execution + execution history endpoints
├── alembic/
│   └── versions/                # Migration history
├── conftest.py            # pytest fixtures, isolated in-memory test database
├── test_users.py           # Auth test suite
├── test_prompts.py          # Prompt CRUD, ownership, and versioning test suite
├── test_llm_provider.py      # Provider adapter test suite (OpenAI client mocked)
├── test_executions.py         # LLM execution endpoint test suite (adapter mocked)
├── test_pricing.py             # Cost calculation test suite
├── docs/
│   ├── decisions/              # Architecture decision records (ADRs)
│   └── incidents/              # Incident write-ups
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

## Data Model

**User** — id, username, email, hashed_password, first_name, last_name, is_active, role

**Prompt** — id, owner_id, title, description, tags, model_target, is_published, current_version, created_at, updated_at, deleted_at

**PromptVersion** — id, prompt_id, version_number, content, created_at

**Execution** — id, user_id, prompt_id, prompt_version_id, model_name, temperature, max_tokens, input, output, error_message, status, incomplete_reason, input_tokens, output_tokens, total_tokens, provider_response_id, latency_ms, cost_usd, retry_attempts, created_at

`output`, `input_tokens`, `output_tokens`, `total_tokens`, `provider_response_id`, and `cost_usd` are nullable — a failed execution never received a response to populate them. `status` holds either a success state (`completed`/`incomplete`) or a failure category (`timeout`, `connection_error`, `rate_limited`, `auth_error`, `provider_error`, `invalid_request`, `unknown_error`). `error_message` holds the raw provider error text for a failure — stored for internal diagnosis only, deliberately **not** part of `ExecutionOut`, so it's never returned by any API response. See [ADR-004](docs/decisions/ADR-004-failure-taxonomy-and-retry-policy.md).

`cost_usd` is computed from the execution's real token usage against a static per-model pricing table (`pricing.py`) and stored as an exact `Numeric(12, 8)` value — never a `Float` — to avoid binary floating-point drift once costs get summed across many rows. It's computed once at execution time and frozen on the row, not recomputed later from a live price, so historical cost stays accurate even if pricing changes going forward.

A `Prompt` holds metadata only; the actual prompt text lives in `PromptVersion`, with one-to-many versions per prompt. This keeps content history append-only and avoids any single "current content" field that could fall out of sync with version history.

`Execution` is an append-only fact record, not an editable entity like `Prompt` — it captures what a specific call actually did (resolved model config, not the caller's raw optional request; see [ADR-003](docs/decisions/ADR-003-execution-persistence-and-access.md)) and is never updated after creation.

## API Endpoints

All endpoints are versioned under `/api/v1`.

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/users/signup` | Create a new user account (rate limited: 5/min per IP) |
| POST | `/api/v1/users/token` | Log in, receive a JWT access token (rate limited: 5/min per IP) |

### Prompts (all require authentication)
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/api/v1/prompts` | any authenticated user | Create a new prompt (auto-creates version 1) |
| GET | `/api/v1/prompts` | owner or published | List visible prompts |
| GET | `/api/v1/prompts/{id}` | owner or published | Retrieve one prompt |
| PUT | `/api/v1/prompts/{id}` | owner only | Update metadata and/or content (creates a new version if content changes) |
| DELETE | `/api/v1/prompts/{id}` | owner only | Soft delete a prompt |
| PATCH | `/api/v1/prompts/{id}/publish` | owner only | Toggle published/private |
| GET | `/api/v1/prompts/{id}/versions` | owner or published | List version history |
| GET | `/api/v1/prompts/{id}/versions/{version_number}` | owner or published | Retrieve one specific version |

### Execution (requires authentication)
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/api/v1/prompts/{id}/versions/{version_number}/execute` | owner or published | (Rate limited: 5/min per IP.) Run a saved prompt version against OpenAI (Responses API) with caller-supplied `input`; persists the execution and returns the full record (generated text, completion status, resolved model config, token usage, estimated cost, latency, provider response ID, retry attempts). On a provider failure, retries transient errors with bounded backoff, then persists a failure record and responds with a mapped error status (`422`/`502`/`503`/`504` depending on failure category — see [ADR-004](docs/decisions/ADR-004-failure-taxonomy-and-retry-policy.md)) instead of a flat `500` |
| GET | `/api/v1/executions/{execution_id}` | executor only | Retrieve one past execution by id, success or failure. Deliberately **not** the prompt's "owner or published" rule — scoped to whoever ran it, regardless of the prompt's publish state (see [ADR-003](docs/decisions/ADR-003-execution-persistence-and-access.md)) |

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL running locally (or update `DATABASE_URL` for your DB of choice)

### Installation

```bash
git clone https://github.com/mbommakanti/PromptVault.git
cd PromptVault
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/PromptVaultDB
SECRET_KEY=<your-secret-key>
ALGORITHM=HS256
OPENAI_API_KEY=<your-openai-api-key>
```

`OPENAI_API_KEY` is required (the app fails fast at startup if it's missing). Default model/temperature/max-token/timeout values live in `config.py` and can be overridden with `OPENAI_DEFAULT_MODEL`, `OPENAI_DEFAULT_TEMPERATURE`, `OPENAI_DEFAULT_MAX_TOKENS`, and `OPENAI_TIMEOUT_SECONDS` if needed.

### Run migrations

```bash
alembic upgrade head
```

### Start the server

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

## Running Tests

```bash
pip install pytest httpx pytest-cov
pytest --cov=. --cov-report=term-missing
```

Tests run against an isolated in-memory SQLite database, never touching real data. Rate limiting is disabled during tests (`limiter.enabled = False` in `conftest.py`) so test-suite request volume doesn't trigger the same limits real abuse would. LLM execution tests mock the OpenAI client entirely — no real network calls or cost. Current coverage: 95% (55 tests).

## Running with Docker

```bash
docker build -t promptvault .
docker run -p 8000:8000 --env-file .env promptvault
```

The container runs `alembic upgrade head` before starting Uvicorn, so the database it points at is migrated automatically on every start (already-applied migrations are skipped). Note that inside a container, `localhost` refers to the container itself — point `DATABASE_URL` at a reachable database host.

## Design Notes

- **Prompt content is separated from prompt metadata** deliberately — this avoids duplicating "current content" in two places and keeping them in sync; the current version is always the version row matching `Prompt.current_version`.
- **Ownership is always derived server-side** from the authenticated user's JWT, never from client-supplied fields — this is enforced consistently across every write endpoint.
- **Deletes are soft** (`deleted_at` timestamp) rather than destructive, consistent with how production systems typically handle user data removal.
- **Alembic's `sqlalchemy.url` is set dynamically at runtime** from the `DATABASE_URL` environment variable, rather than hardcoded in `alembic.ini` — necessary since the deployed database URL differs from the local one.
- **API versioning uses URL path prefixing** (`/api/v1`) rather than headers or query params — simplest to test, document, and reason about; a future `/api/v2` can be added as a parallel set of routes without breaking existing clients.
- **Rate limiting is keyed by IP address**, applied to signup and login (the highest-risk endpoints for brute-force and spam abuse) and to LLM execution (the only endpoint that spends real money). Because the deployed app sits behind a reverse proxy, Uvicorn runs with `--proxy-headers` so the limiter sees the real client IP rather than the proxy's — otherwise every user would share a single rate-limit bucket.
- **Database connections are health-checked before reuse** (`pool_pre_ping=True`) — the production database scales to zero when idle and drops open connections, so a pooled connection is verified with a cheap ping and transparently replaced if it's dead, instead of failing the first request after an idle period.
- **The OpenAI SDK never leaks past `llm_provider.py`** — the execution route only ever sees a normalized `AdapterResponse`, never a raw provider object. See [ADR-002](docs/decisions/ADR-002-llm-provider-integration.md) for why the Responses API was chosen over Chat Completions, and how stored prompt content vs. per-call input is split.
- **Executions persist resolved config, not the raw request** — `temperature`/`max_tokens` on a persisted `Execution` reflect what the provider actually used (read back from its response), not the caller's optional request field, which may have been left unset. See [ADR-003](docs/decisions/ADR-003-execution-persistence-and-access.md).
- **Execution read access is scoped to the executor, not the prompt owner** — a published prompt makes its *content* readable to anyone, not the private input/output of everyone who's executed it. See ADR-003 for the specific leak this prevents.
- **Every execution attempt is persisted, success or failure** — a failed provider call is normalized into an internal taxonomy (`provider_errors.py`), retried with bounded, jittered backoff if the failure is transient, and persisted with its real attempt count and failure category regardless of outcome. Only a genuinely unexpected, unclassified exception (a bug, not a provider failure) still falls through to the generic 500 handler unpersisted. See [ADR-004](docs/decisions/ADR-004-failure-taxonomy-and-retry-policy.md).
- **The OpenAI SDK's own built-in retries are disabled** (`max_retries=0`) — the app's bounded retry loop (`execute_with_retry`) is the sole source of retry attempts, so a configured attempt count can't silently multiply against a second, hidden retry layer inside the SDK.
- **The raw provider failure reason is persisted, but only for internal use** — `Execution.error_message` stores the real provider error text so a failure can actually be diagnosed later, but it's deliberately excluded from `ExecutionOut`: the API's external response stays generic (see the point above about `auth_error`), while the underlying row still remembers the real cause for anyone with legitimate access to it. See [ADR-004](docs/decisions/ADR-004-failure-taxonomy-and-retry-policy.md#update-2026-09-20-the-external-message-decision-had-an-internal-cost).
- **Cost is computed with `Decimal`, stored as `Numeric`, never `Float`** — token counts are exact (provider-reported), but the per-token price has to be converted via `Decimal(str(price))` rather than `Decimal(price)` to avoid inheriting a float's own binary imprecision; the result is persisted in a `Numeric(12, 8)` column for the same reason, so summing cost across many executions later doesn't accumulate rounding drift. A model's provider-reported `model_name` sometimes includes a dated snapshot suffix (e.g. `gpt-4o-mini-2024-07-18`) and sometimes doesn't, so it's normalized before the pricing lookup — confirmed against real stored rows, not assumed.
- **An execution's cost is unknown (`null`), never fabricated, when it can't be determined** — an unpriced model or a failed call with no token usage both resolve to `cost_usd = null` rather than `0`, the same discipline already applied to `output_tokens`/`total_tokens` on a failed execution.

## Deployment

Live at [promptops-api.bommakantimaneesh.dev](https://promptops-api.bommakantimaneesh.dev/docs).

- **App:** [Render](https://render.com) web service, built from this repository's `Dockerfile` and auto-deployed on push to `main`. Migrations run in the container's start command (`alembic upgrade head && uvicorn ...`), so a failed migration stops the server from starting against a mismatched schema.
- **Database:** [Neon](https://neon.tech) serverless PostgreSQL, in the same region as the app.
- **Domain:** a subdomain managed in Cloudflare DNS (CNAME to Render, DNS-only), with TLS issued by Render.
- **Secrets:** `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, and `OPENAI_API_KEY` are set as Render environment variables — never committed. Production uses a dedicated OpenAI project and key with a monthly budget limit, separate from local development.
- **Free-tier trade-off:** both the app and the database scale to zero when idle, so the first request after inactivity is slow (~30–60s).

Previously deployed on Railway; moved to Render + Neon to run on free tiers.

## How This Was Built

This is a learning project, and I built it with AI assistance deliberately rather than around it.

- **Backend logic is written by me.** For each feature, I used [Claude Code](https://claude.com/claude-code) as a tutor and reviewer: it explained the concept and design options first, I implemented it, and it reviewed my code for bugs, edge cases, and design issues. Several real bugs were caught this way — they're written up in [docs/LEARNINGS.md](docs/LEARNINGS.md).
- **AI helped draft supporting material** — documentation (this README, ADRs, progress notes) and some of the tests. I reviewed all of it and can explain every design decision and test case.
- **The frontend (planned) will be AI-generated** against the real backend API, since the learning focus of this project is the backend and LLM engineering.

Design decisions and their trade-offs are recorded in [docs/decisions/](docs/decisions/).

## Roadmap

- ~~Global exception handling with a structured JSON error contract~~ ✅
- ~~pytest coverage (auth failures, ownership violations, happy paths)~~ ✅
- ~~Docker + deployment (Railway)~~ ✅
- ~~API versioning (`/api/v1`)~~ ✅
- ~~Rate limiting on auth endpoints~~ ✅
- ~~Prompt execution against LLM APIs~~ ✅
- ~~Execution persistence and history~~ ✅
- ~~Failure handling and bounded retries for LLM execution~~ ✅
- ~~Token and cost accounting for LLM execution~~ ✅
- ~~Rate limiting on LLM execution; redeploy to Render + Neon with a custom domain~~ ✅
- Prompt variables and deterministic rendering (with a preview endpoint)
- Structured outputs with server-side schema validation
- Evaluation datasets, deterministic evaluators, and baseline-vs-candidate comparison
- Held-out evaluation, regression gates, and evidence-based prompt promotion/rollback