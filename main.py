from fastapi import FastAPI,Request, HTTPException
from fastapi.responses import JSONResponse
from routers import users, prompts

app = FastAPI()

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