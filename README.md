# PromptVault

A FastAPI backend for storing, versioning, and retrieving LLM prompts — with JWT authentication and ownership-based access control.

**Live demo:** [promptvault-production-3160.up.railway.app/docs](https://promptvault-production-3160.up.railway.app/docs)

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
- **Rate limiting** — login and signup are limited to 5 requests/minute per IP to reduce brute-force and spam risk
- **Structured error responses** — a global exception handler returns a consistent JSON error shape across the whole API, including rate-limit (429) responses
- **LLM execution** — run a saved, immutable prompt version against OpenAI through a normalized provider adapter; returns generated text, completion status, token usage, and the provider's response ID
- **Execution history** — every execution is persisted as an inspectable, immutable record (resolved model config, input, output, token usage, latency, provider response ID) and retrievable by id, scoped to whoever ran it
- **Automated test suite** — 40 pytest tests covering auth, ownership, versioning, soft-delete, and LLM execution/persistence (provider calls mocked), run against an isolated in-memory database

## Tech Stack

- **FastAPI** — web framework
- **SQLAlchemy** — ORM
- **Alembic** — database migrations
- **Pydantic** — request/response validation
- **PostgreSQL** — database (production, via Railway)
- **python-jose** — JWT encoding/decoding
- **passlib (bcrypt)** — password hashing
- **slowapi** — rate limiting
- **openai** — LLM provider SDK (Responses API)
- **pydantic-settings** — typed, validated provider configuration from environment variables
- **pytest** — automated testing (40 tests, 97% coverage)
- **Docker** — containerized deployment
- **Railway** — hosting

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
├── llm_provider.py             # OpenAI provider adapter (open_ai_adapter, get_openai_client)
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
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

## Data Model

**User** — id, username, email, hashed_password, first_name, last_name, is_active, role

**Prompt** — id, owner_id, title, description, tags, model_target, is_published, current_version, created_at, updated_at, deleted_at

**PromptVersion** — id, prompt_id, version_number, content, created_at

**Execution** — id, user_id, prompt_id, prompt_version_id, model_name, temperature, max_tokens, input, output, status, incomplete_reason, input_tokens, output_tokens, total_tokens, provider_response_id, latency_ms, created_at

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
| POST | `/api/v1/prompts/{id}/versions/{version_number}/execute` | owner or published | Run a saved prompt version against OpenAI (Responses API) with caller-supplied `input`; persists the execution and returns the full record (generated text, completion status, resolved model config, token usage, latency, provider response ID) |
| GET | `/api/v1/executions/{execution_id}` | executor only | Retrieve one past execution by id. Deliberately **not** the prompt's "owner or published" rule — scoped to whoever ran it, regardless of the prompt's publish state (see [ADR-003](docs/decisions/ADR-003-execution-persistence-and-access.md)) |

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

Tests run against an isolated in-memory SQLite database, never touching real data. Rate limiting is disabled during tests (`limiter.enabled = False` in `conftest.py`) so test-suite request volume doesn't trigger the same limits real abuse would. LLM execution tests mock the OpenAI client entirely — no real network calls or cost. Current coverage: 97% (40 tests).

## Running with Docker

```bash
docker build -t promptvault .
docker run -p 8000:8000 --env-file .env promptvault
```

## Design Notes

- **Prompt content is separated from prompt metadata** deliberately — this avoids duplicating "current content" in two places and keeping them in sync; the current version is always the version row matching `Prompt.current_version`.
- **Ownership is always derived server-side** from the authenticated user's JWT, never from client-supplied fields — this is enforced consistently across every write endpoint.
- **Deletes are soft** (`deleted_at` timestamp) rather than destructive, consistent with how production systems typically handle user data removal.
- **Alembic's `sqlalchemy.url` is set dynamically at runtime** from the `DATABASE_URL` environment variable, rather than hardcoded in `alembic.ini` — necessary since the deployed database URL differs from the local one.
- **API versioning uses URL path prefixing** (`/api/v1`) rather than headers or query params — simplest to test, document, and reason about; a future `/api/v2` can be added as a parallel set of routes without breaking existing clients.
- **Rate limiting is keyed by IP address**, applied to signup and login specifically since those are the highest-risk endpoints for brute-force and spam abuse.
- **The OpenAI SDK never leaks past `llm_provider.py`** — the execution route only ever sees a normalized `AdapterResponse`, never a raw provider object. See [ADR-002](docs/decisions/ADR-002-llm-provider-integration.md) for why the Responses API was chosen over Chat Completions, and how stored prompt content vs. per-call input is split.
- **Executions persist resolved config, not the raw request** — `temperature`/`max_tokens` on a persisted `Execution` reflect what the provider actually used (read back from its response), not the caller's optional request field, which may have been left unset. See [ADR-003](docs/decisions/ADR-003-execution-persistence-and-access.md).
- **Execution read access is scoped to the executor, not the prompt owner** — a published prompt makes its *content* readable to anyone, not the private input/output of everyone who's executed it. See ADR-003 for the specific leak this prevents.
- **Only successful executions are persisted (for now)** — a failed provider call still propagates to the generic 500 handler and writes no row. Deliberately deferred to a dedicated failure-taxonomy step rather than solved ad hoc (see Roadmap).

## Deployment

Deployed on [Railway](https://railway.app) from this repository's `Dockerfile`. PostgreSQL is provisioned as a separate Railway service and connected via a referenced environment variable. Live at [promptvault-production-3160.up.railway.app](https://promptvault-production-3160.up.railway.app/docs).

## Roadmap

- ~~Global exception handling with a structured JSON error contract~~ ✅
- ~~pytest coverage (auth failures, ownership violations, happy paths)~~ ✅
- ~~Docker + deployment (Railway)~~ ✅
- ~~API versioning (`/api/v1`)~~ ✅
- ~~Rate limiting on auth endpoints~~ ✅
- ~~Prompt execution against LLM APIs~~ ✅
- ~~Execution persistence and history~~ ✅
- Failure handling and bounded retries for LLM execution