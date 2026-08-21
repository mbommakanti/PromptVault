# Architecture Decisions

This folder contains important technical decisions made while building PromptOps.

Create an ADR only when there is a meaningful architectural or engineering choice with real tradeoffs.

Examples:

- SSE vs WebSockets for streaming
- Direct provider SDK vs framework abstraction
- How model/provider responses are normalized
- Whether/when to introduce a background job queue
- Redis worker vs AWS SQS
- How prompt promotion and rollback work
- When a second LLM provider is justified

Do not create ADRs for trivial implementation choices.

## Naming

Use:

`ADR-XXX-short-description.md`

Example:

`ADR-001-use-sse-for-streaming.md`

## Template

# ADR-XXX: Decision Title

## Status

Proposed / Accepted / Superseded

## Context

What problem are we trying to solve?

Why does a decision need to be made?

## Options Considered

### Option 1

Describe the option.

Pros:
- ...

Cons:
- ...

### Option 2

Describe the option.

Pros:
- ...

Cons:
- ...

## Decision

What did we choose?

## Why

Why is this the best choice for PromptOps right now?

## Tradeoffs

What are we giving up or accepting?

## Revisit When

Under what conditions should this decision be reconsidered?