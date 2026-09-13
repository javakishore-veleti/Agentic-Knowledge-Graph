"""Orchestrator API entry point."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from akg_service_core import SERVICE_FACTORY, ServiceError
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import run_router
from .bootstrap import register_all
from .config import settings
from .service.i_run_service import IRunService

log = logging.getLogger(__name__)

app = FastAPI(
    title="AKG Orchestrator",
    version="0.1.0",
    description=(
        "One contract over every workflow engine. Callers name a workflow and an engine "
        "and read back one vocabulary of run states; Airflow's auth scheme, URL layout "
        "and state names stay inside its adapter."
    ),
)

register_all()

# Named origins only: this API starts workflows.
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-trace-id"],
    )


@app.middleware("http")
async def trace_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    tid = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = tid
    response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    # A 5xx hides its message from the client on purpose -- the text of a persistence
    # failure describes the schema. It must still reach the log, or the operator the
    # response tells to "quote the trace id" has nothing to look the trace id up in.
    if exc.status >= 500:
        log.error("%s [%s] %s", exc.code, exc.trace_id, exc.message, exc_info=exc)

    return JSONResponse(
        status_code=exc.status,
        content={
            "type": "about:blank",
            "title": exc.code.replace("_", " ").title(),
            "status": exc.status,
            "code": exc.code,
            "detail": exc.message if exc.status < 500 else
                      "The request failed. Quote the trace id when reporting this.",
            "trace_id": exc.trace_id or getattr(request.state, "trace_id", None),
        },
        media_type="application/problem+json",
    )


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Reports each engine separately.

    A single boolean would hide the case this service exists to make visible: Airflow
    answering /health while refusing every API call.
    """
    engines = SERVICE_FACTORY.get(IRunService).engines()
    return {
        "status": "ok" if all(e.available for e in engines.items) else "degraded",
        "env": settings.env,
        "engines": {e.engine: {"available": e.available, "detail": e.detail}
                    for e in engines.items},
    }


app.include_router(run_router)
