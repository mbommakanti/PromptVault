from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from rate_limit import limiter
from routers import executions, prompts, users

app = FastAPI(
    title="PromptOps API",
    version="0.4.0",
    description=(
        "Prompt versioning and observable LLM execution — evolving from PromptVault into an "
        "evaluation-first LLM engineering platform.\n\n"
        "Every execution is persisted with its resolved model config, token usage, cost, latency, "
        "retry attempts and failure category.\n\n"
        "**Getting started:** sign up via `POST /api/v1/users/signup`, then click **Authorize** "
        "and log in with your username and password.\n\n"
        "Hosted on a free tier — the first request after a period of inactivity can take ~30–60s.\n\n"
        "[Source on GitHub](https://github.com/mbommakanti/PromptVault)"
    ),
)

app.state.limiter = limiter

app.include_router(users.router)
app.include_router(prompts.router)
app.include_router(executions.router)
app.include_router(executions.execution_router)

@app.exception_handler(HTTPException)
def http_exception_handler(request:Request,exc:HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "status_code": exc.status_code, "detail": exc.detail}
    )

@app.exception_handler(Exception)
def generic_exception_handler(request:Request,exc:Exception):
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": True, "status_code": 500, "detail": "An unexpected error occurred"}
    )

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": True, "status_code": 429, "detail": "Too many requests. Please try again later."}
    )