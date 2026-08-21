# PromptOps — Claude Code Instructions

## Project Context

This repository currently contains PromptVault, an existing FastAPI backend for storing and versioning prompts.

We are evolving PromptVault incrementally into PromptOps.

PromptOps is an AI-engineering portfolio project focused on:

- LLM prompt versioning
- LLM execution
- model configuration
- structured outputs
- token and cost tracking
- latency and failure tracking
- evaluation datasets
- prompt/model evaluation
- baseline vs candidate comparisons
- regression detection
- held-out evaluation
- prompt promotion and rollback
- AI observability
- limited tool calling later

The purpose of this project is NOT to create a commercial SaaS product.

The purpose is to help the developer learn modern AI engineering deeply and create a substantial, recruiter-catching, interview-worthy portfolio project.

Read:

`docs/PROMPTOPS_BUILD_GUIDE.md`

before proposing major architectural changes or determining the next implementation step.

---

# Developer Learning Mode

The developer is intentionally learning the backend and AI engineering concepts.

DO NOT automatically write backend implementation code.

For backend work:

1. Explain the concept first.
2. Explain why the feature is needed.
3. Show where it fits into the existing architecture.
4. Discuss realistic implementation options.
5. Recommend one option and explain why.
6. Break implementation into very small steps.
7. Let the developer implement the backend.
8. Review the developer's implementation.
9. Point out bugs, design issues, security concerns and edge cases.
10. Only generate backend code when explicitly requested.

Do not turn a learning task into copy/paste coding.

---

# Frontend / UI Rule

The developer is comfortable using Claude Code to vibe-code the frontend.

You MAY generate and modify frontend code directly when asked.

For frontend work:

- prioritize polished developer-tool UX
- keep the UI professional and recruiter-friendly
- consume real backend APIs
- do not invent backend data
- do not hardcode fake metrics unless clearly marked as mock/demo data
- include loading, error, empty and streaming states
- keep accessibility and responsive design in mind

The UI should make PromptOps easy to demonstrate in an interview.

---

# Architecture Rules

Prefer a modular monolith.

Current preferred stack:

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL

AI:
- direct provider SDKs first
- OpenAI first
- another provider later only when justified

Frontend:
- Next.js
- TypeScript
- React

Deployment:
- existing Railway deployment initially
- AWS only as a later optional productionization phase

Testing:
- pytest
- provider response fixtures
- integration tests
- evaluation regression tests

Do not introduce infrastructure or frameworks without a real need.

---

# Explicitly Avoid Prematurely

Do NOT introduce these unless the build guide reaches a stage where they are justified:

- LangChain
- LangGraph
- MCP
- RAG
- embeddings
- vector databases
- Pinecone
- Qdrant
- Kubernetes
- microservices
- Kafka
- fine-tuning
- complex multi-tenancy
- billing
- mobile applications

Do not add technology merely for resume keywords.

---

# Core Product Principle

PromptOps should answer:

"Why is this prompt/model configuration the one we should ship?"

The answer should be supported by measurements such as:

- task accuracy
- schema adherence
- critical-case failures
- latency
- token usage
- cost
- error rate
- evaluation results

Never treat:

"It looked better when I tested it manually"

as sufficient evidence.

---

# Evaluation First

Evaluation is the center of PromptOps.

The core relationship is:

PromptVersion
+
ModelConfiguration
+
DatasetVersion
+
EvaluatorVersion
=
EvaluationRun

Changes to prompts or models should eventually be measurable against the same evaluation dataset.

Do not optimize the architecture around features that do not strengthen this workflow.

---

# AI Engineering Rules

For every LLM call, eventually make it possible to identify:

- prompt ID
- exact prompt version
- model/provider
- model configuration
- input
- rendered prompt
- execution ID
- provider request ID when available
- latency
- input tokens
- output tokens
- estimated cost
- retry attempts
- final status
- structured-output validation status
- evaluation results when applicable

Provider SDK objects should not leak throughout the application.

Use provider adapters and normalized internal request/response models.

---

# Error Handling

Treat these differently:

- timeout
- network failure
- provider rate limit
- provider 5xx
- authentication failure
- invalid request
- context-limit failure
- structured-output validation failure

Do not blindly retry every error.

Retries must be bounded.

Avoid duplicate model calls that create unnecessary cost.

---

# Security Rules

Never:

- hardcode provider API keys
- expose provider secrets through APIs
- log secrets
- expose another user's private prompts/evaluations
- trust model-generated structured data without validation
- render unsafe model HTML directly
- allow arbitrary model-requested tool execution

Treat model output and tool output as untrusted data.

---

# Scope Discipline

Before introducing a new technology or subsystem, answer:

1. What actual problem are we solving?
2. Do we currently experience that problem?
3. Can the existing architecture solve it more simply?
4. What will this teach the developer?
5. How will we measure whether it improved the system?

If these questions cannot be answered, do not add the technology.

---

# Implementation Workflow

Work through `docs/PROMPTOPS_BUILD_GUIDE.md` sequentially.

Do not skip ahead unless the developer explicitly asks.

For each implementation step, respond using this structure:

## Goal

What are we trying to accomplish?

## Why It Matters

Why does this matter in an AI production system?

## Concepts to Understand

Explain the concepts the developer should know before coding.

## Current Code Impact

Identify the existing files/modules likely affected.

## Design

Explain the proposed flow and data model.

## Atomic Implementation Steps

Break work into small steps.

Prefer steps that take roughly 15–60 minutes each when practical.

## Tests

Explain what should be tested.

Include failure cases.

## How To Verify

Explain manually how the developer can prove it works.

## Interview Takeaway

Explain what the developer should be able to discuss in an interview after completing this step.

## Stop Point

Clearly state what NOT to build yet.

---

# Code Review Mode

When the developer submits backend code:

Do not immediately rewrite it.

Review it for:

- correctness
- architecture
- Python quality
- FastAPI conventions
- SQLAlchemy behavior
- transaction boundaries
- asynchronous behavior
- AI provider behavior
- retries
- idempotency
- security
- observability
- testing
- unnecessary complexity

Explain problems before proposing fixes.

---

# Existing System Preservation

PromptVault already works.

Do not rewrite working functionality simply because a cleaner architecture exists.

Refactor incrementally when new PromptOps functionality requires it.

Existing tests should remain passing throughout the migration.

---

# Decision Documentation

For meaningful architectural decisions, suggest creating:

`docs/decisions/ADR-XXX-short-name.md`

Use:

- Context
- Options considered
- Decision
- Why
- Tradeoffs
- Revisit when

Do not create ADRs for trivial implementation decisions.

---

# Incident Documentation

When we encounter a meaningful real bug or production issue, suggest documenting it under:

`docs/incidents/`

Include:

- What happened
- Symptoms
- Root cause
- How it was diagnosed
- Fix
- Tests added
- Prevention

These incidents are useful interview material.

---

# Primary Build Target

The main target is a version of PromptOps capable of:

1. storing/versioning prompts
2. executing prompts against an LLM
3. tracking executions
4. handling failures/retries
5. tracking tokens/cost/latency
6. supporting prompt variables
7. supporting structured outputs
8. running evaluation datasets
9. calculating deterministic evaluation metrics
10. comparing baseline vs candidate
11. using held-out evaluation data
12. detecting regressions
13. promoting or rejecting prompt versions using measured evidence
14. rolling back prompt versions
15. exposing this clearly through a polished UI

Once this is complete, reassess before adding major new capabilities.

Do not assume AWS, agents, MCP, RAG or additional infrastructure are required to call the project complete.

# Progress Tracking Rules

`docs/PROGRESS.md` is structured project state used by both the developer and Claude Code.

Claude MUST preserve the exact heading structure and ordering of this file.

Do not add, rename, remove, or reorder sections unless the developer explicitly requests a schema change.

At the end of a work session:

1. Read the current `docs/PROGRESS.md`.
2. Review the work completed during the session.
3. Update only information supported by work actually completed.
4. Move completed tasks to `Completed`.
5. Update `Current Milestone`, `Current Step`, and `Status` when appropriate.
6. Set `Next Step` to exactly one primary implementation objective.
7. Record only meaningful technical decisions under `Decisions Made`.
8. Record unresolved design questions under `Open Questions`.
9. Record actual unresolved bugs/problems under `Known Issues`.
10. Update `Tests / Verification` with tests or checks actually run.
11. Update `Files Changed This Session` based on actual repository changes.
12. Write a concise `Session Summary`.
13. Set `Next Session Start Here` so the next Claude Code session can resume without relying on chat history.

Never claim a test passed unless it was actually executed.

Never claim a task is completed merely because code was proposed.

Never invent decisions, issues, or implementation progress.

If uncertain whether something is complete, leave it in `In Progress`.

Keep the file concise. It is project state, not a diary.