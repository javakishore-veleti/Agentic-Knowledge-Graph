"""DataCatalog API entry point."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import schemas
from .config import settings
from .db import SessionLocal
from .routes import router

app = FastAPI(
    title="AKG DataCatalog",
    version="0.1.0",
    description=(
        "Domains, datasets, MIOs (Managed Informational Objects), their data instances "
        "and executions, and the endpoints where each technology lives."
    ),
)


@app.middleware("http")
async def trace_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """One trace_id from the edge through every hop (PRD B 5.3).

    Accepts an inbound id so the portal's id survives, mints one otherwise, and always
    returns it so a caller can quote it in a bug report.
    """
    tid = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = tid
    response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response


@app.exception_handler(Exception)
async def problem_handler(request: Request, exc: Exception) -> JSONResponse:
    """RFC 9457 Problem Details, with the trace id, and without the exception text.

    A stack trace or driver error in an HTTP body leaks schema and connection details to
    whoever provoked it; the trace id is how an operator finds the real error in the logs.
    """
    tid = getattr(request.state, "trace_id", None)
    problem = schemas.Problem(
        title="Internal server error",
        status=500,
        code="internal_error",
        detail="The request failed. Quote the trace id when reporting this.",
        trace_id=tid,
    )
    return JSONResponse(status_code=500, content=problem.model_dump(), media_type="application/problem+json")


@app.get("/health", response_model=schemas.HealthOut, tags=["ops"])
def health() -> schemas.HealthOut:
    """Reports what is actually true, not merely that the process is up.

    A catalog API that answers 200 while the schema is missing is worse than one that
    fails: it makes an empty list look like an empty catalog.
    """
    db_ok = False
    schema_ok = False
    drift = 0
    try:
        with SessionLocal() as s:
            db_ok = s.scalar(text("SELECT 1")) == 1
            schema_ok = bool(
                s.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.views "
                        "WHERE table_schema = 'catalog' AND table_name = 'mio_overview'"
                    )
                )
            )
            if schema_ok:
                drift = s.scalar(
                    text("SELECT count(*) FROM catalog.data_instance_exec_drift")
                ) or 0
    except Exception:
        pass
    return schemas.HealthOut(
        status="ok" if (db_ok and schema_ok and drift == 0) else "degraded",
        env=settings.env,
        database=db_ok,
        catalog_schema=schema_ok,
        drift=drift,
    )


app.include_router(router)
