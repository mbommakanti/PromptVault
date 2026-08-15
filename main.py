from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from rate_limit import limiter
from routers import prompts, users

app = FastAPI()

app.state.limiter = limiter

app.include_router(users.router)
app.include_router(prompts.router)

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