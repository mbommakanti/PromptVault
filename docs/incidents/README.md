# Engineering Incident Journal

This folder records meaningful bugs, failures, production issues, and difficult debugging cases encountered while building PromptOps.

The purpose is to preserve:

- what failed
- how it was detected
- how it was investigated
- the root cause
- the fix
- the tests added
- what was learned

These should be real incidents encountered during development or deployment.

Do not manufacture incidents for portfolio purposes.

## What Is Worth Recording?

Examples:

- LLM provider calls unexpectedly timing out
- incorrect retry behavior causing duplicate inference calls
- evaluation jobs running twice
- streaming connection not closing correctly
- prompt version transaction leaving inconsistent database state
- token/cost calculations being incorrect
- structured-output validation failures
- provider rate-limit handling behaving incorrectly
- worker crash causing evaluation cases to rerun
- authorization bug exposing another user's resource
- deployment or migration failure that required investigation

Minor syntax errors and obvious one-line mistakes do not need incident documents.

## Naming

Use:

`YYYY-MM-DD-short-description.md`

Example:

`2026-09-14-duplicate-evaluation-executions.md`

## Template

# Incident: Short Description

## Date

YYYY-MM-DD

## Status

Resolved / Investigating

## Summary

Briefly describe what happened.

## Expected Behavior

What should have happened?

## Actual Behavior

What happened instead?

## Impact

What was affected?

Examples:

- incorrect result
- duplicate LLM cost
- failed request
- broken deployment
- inconsistent database state

## Detection

How was the issue discovered?

Examples:

- failing test
- application logs
- UI behavior
- provider response
- database inspection
- production alert

## Investigation

What did you check?

What hypotheses did you test?

## Root Cause

What actually caused the issue?

## Fix

What was changed?

## Verification

How did you prove the fix worked?

## Tests Added

What automated tests were added to prevent regression?

## Lessons Learned

What engineering lesson should be remembered?

## Prevention

What change reduces the chance of this happening again?