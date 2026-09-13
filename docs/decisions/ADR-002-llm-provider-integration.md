# ADR-002: LLM Provider Integration Shape

## Status

Accepted

## Context

Step 1 added PromptVault's first outbound call to a real LLM provider (OpenAI). Three related decisions had to be made about the shape of that integration, all inside the same new adapter (`llm_provider.py`):

1. Which OpenAI API to build on — the long-standing Chat Completions API, or the newer Responses API.
2. What a stored `PromptVersion.content` maps to in the request, and where the actual per-call input comes from.
3. Whether to use the Responses API's server-side state features (`store`, `previous_response_id`).

These aren't independent implementation details — together they determine what "the request" and "the response" mean for every execution PromptOps will ever record, and they're hard to change later without touching every caller of the adapter.

## Options Considered

### 1. Which API to build on

**Option A — Chat Completions.** The long-standing, still-fully-supported API (`client.chat.completions.create`). Widely documented, stable, not going away.

**Option B — Responses API (chosen).** OpenAI's newer unified interface (`client.responses.create`), introduced 2025 and positioned as where new capabilities (structured outputs, tool use, reasoning) land first.

Chat Completions is **not deprecated** — OpenAI has committed to supporting it indefinitely. The deciding factor was direction, not obsolescence: building new work on Responses avoids adopting an interface OpenAI itself is de-emphasizing for new projects, and Step 7 (structured outputs) and Step 22 (tool calling) both map more directly onto it.

### 2. What `PromptVersion.content` becomes in the request

**Option A — `content` → `instructions`; a new `input` field, supplied per-call (chosen).** The stored prompt plays the role of standing instructions; the actual task/data comes from the caller at execution time.

**Option B — `content` → `input` directly.** No separate input field; whatever is stored is sent as-is.

Option B is simpler today but wrong for where the project is going: Steps 9-13 run one stored prompt against many different dataset cases. Option A means the request shape already matches that usage — a dataset case's text becomes `input`, the stored prompt stays `instructions` — with no rework needed when evaluation runs arrive.

### 3. Server-side state features

**Option A — Use `store` (default `true`) and/or `previous_response_id` for multi-turn state.** Lets OpenAI hold conversation state server-side.

**Option B — `store=False`, no `previous_response_id` (chosen).** Every execution's input is fully explicit in the request PromptOps itself constructs and can log.

PromptOps intends to be the system of record for execution lineage (per its core observability principle) and will handle potentially sensitive benchmark data (support messages). Relying on OpenAI-side state for reproducibility would mean an execution's true input isn't fully contained in PromptOps's own request — undermining the "reconstruct any execution" goal before persistence (Step 2) even exists.

## Decision

- Build the adapter on the **Responses API**.
- Map stored `PromptVersion.content` → `instructions`; accept a separate, caller-supplied `input` per execution.
- Call with **`store=False`** and never use `previous_response_id`.

## Why

Each choice optimizes for the same thing: keeping every execution fully self-describing from data PromptOps itself holds, in a shape that doesn't need to be reworked once evaluation runs (Steps 9-13) and structured output (Step 7) arrive.

## Tradeoffs

- Responses API is newer and less broadly documented in third-party tutorials than Chat Completions; some debugging will lean more on official docs than community examples.
- The `instructions`/`input` split assumes every execution has exactly one "prompt" and one "input" — fine through Step 13, but multi-turn conversation (several `assistant`/`user` turns) isn't modeled yet and would need its own design.
- Not using `previous_response_id` means any future multi-turn feature is built explicitly in PromptOps's own data model, not borrowed from OpenAI's — more upfront work, but consistent with treating provider state as untrusted/out-of-scope.

## Revisit When

- Step 21 adds a second provider — confirms whether `instructions`/`input` generalizes, or whether the adapter interface needs to change shape to accommodate a provider without an equivalent split.
- Multi-turn conversation becomes an actual requirement (not currently on the roadmap through M3).
