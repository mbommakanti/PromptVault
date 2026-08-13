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
- **Structured error responses** — a global exception handler returns a consistent JSON error shape across the whole API
- **Automated test suite** — 21 pytest tests covering auth, ownership, versioning, and soft-delete behavior, run against an isolated in-memory database

## Tech Stack

- **FastAPI** — web framework
- **SQLAlchemy** — ORM
- **Alembic** — database migrations
- **Pydantic** — request/response validation
- **PostgreSQL** — database (production, via Railway)
- **python-jose** — JWT encoding/decoding
- **passlib (bcrypt)** — password hashing
- **pytest** — automated testing (21 tests, 96% coverage)
- **Docker** — containerized deployment
- **Railway** — hosting

## Project Structure

```
PromptVault/
├── main.py              # FastAPI app instance, router registration, global exception handlers
├── database.py           # DB engine, session, and dependency
├── models.py              # SQLAlchemy ORM models (User, Prompt, PromptVersion)
├── schemas.py              # Pydantic request/response schemas
├── auth.py                  # Password hashing, JWT creation/verification, get_current_user
├── routers/
│   ├── users.py               # Signup, login endpoints
│   └── prompts.py              # Prompt CRUD and versioning endpoints
├── alembic/
│   └── versions/                # Migration history
├── conftest.py            # pytest fixtures, isolated in-memory test database
├── test_users.py           # Auth test suite
├── test_prompts.py          # Prompt CRUD, ownership, and versioning test suite
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

## Data Model

**User** — id, username, email, hashed_password, first_name, last_name, is_active, role

**Prompt** — id, owner_id, title, description, tags, model_target, is_published, current_version, created_at, updated_at, deleted_at

**PromptVersion** — id, prompt_id, version_number, content, created_at

A `Prompt` holds metadata only; the actual prompt text lives in `PromptVersion`, with one-to-many versions per prompt. This keeps content history append-only and avoids any single "current content" field that could fall out of sync with version history.

## API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/users/signup` | Create a new user account |
| POST | `/users/token` | Log in, receive a JWT access token |

### Prompts (all require authentication)
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/prompts` | any authenticated user | Create a new prompt (auto-creates version 1) |
| GET | `/prompts` | owner or published | List visible prompts |
| GET | `/prompts/{id}` | owner or published | Retrieve one prompt |
| PUT | `/prompts/{id}` | owner only | Update metadata and/or content (creates a new version if content changes) |
| DELETE | `/prompts/{id}` | owner only | Soft delete a prompt |
| PATCH | `/prompts/{id}/publish` | owner only | Toggle published/private |
| GET | `/prompts/{id}/versions` | owner or published | List version history |
| GET | `/prompts/{id}/versions/{version_number}` | owner or published | Retrieve one specific version |

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
```

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

Tests run against an isolated in-memory SQLite database, never touching real data. Current coverage: 96%.

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

## Deployment

Deployed on [Railway](https://railway.app) from this repository's `Dockerfile`. PostgreSQL is provisioned as a separate Railway service and connected via a referenced environment variable. Live at [promptvault-production-3160.up.railway.app](https://promptvault-production-3160.up.railway.app/docs).

## Roadmap

- ~~Global exception handling with a structured JSON error contract~~ ✅
- ~~pytest coverage (auth failures, ownership violations, happy paths)~~ ✅
- ~~Docker + deployment (Railway)~~ ✅
- Prompt execution against LLM APIs (Month 3)