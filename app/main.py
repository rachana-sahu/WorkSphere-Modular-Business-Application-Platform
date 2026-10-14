import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import assistant, ats, auth, communication, crm, hr, projects, workspaces
from app.database import check_database
from app.observability import RequestContextMiddleware, configure_logging

configure_logging()

app = FastAPI(
    title="WorkSphere API",
    description="API foundation for the WorkSphere modular business platform.",
    version="0.1.0",
)
app.add_middleware(RequestContextMiddleware)
app.include_router(auth.router)
app.include_router(crm.router)
app.include_router(projects.router)
app.include_router(assistant.router)
app.include_router(communication.router)
app.include_router(hr.router)
app.include_router(ats.router)
app.include_router(workspaces.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "location": error["loc"],
            "code": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "errors": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logging.getLogger("worksphere.errors").error(
        "Unhandled request exception",
        extra={"request_id": getattr(request.state, "request_id", None)},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        headers={
            "X-Request-ID": getattr(request.state, "request_id", "unavailable")
        },
        content={
            "detail": {
                "code": "internal_error",
                "message": "The request could not be completed due to an internal error.",
            }
        },
    )


@app.get("/api/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if not check_database():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": "The database is currently unavailable.",
            },
        )
    return {"status": "ready"}
