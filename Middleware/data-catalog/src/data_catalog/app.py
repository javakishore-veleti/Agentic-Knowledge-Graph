"""DataCatalog API entry point."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    app_endpoint_router, catalog_router, dataset_endpoint_router,
    initial_data_router, workflow_router,
)
from .bootstrap import register_all
from .purposes.api import purpose_router
from .common.errors import ServiceError
from .common.object_factory import SERVICE_FACTORY
from .config import settings
from .service.i_catalog_service import IHealthService

app = FastAPI(
    title="AKG DataCatalog",
    version="0.1.0",
    description=(
        "Domains, datasets, MIOs (Managed Informational Objects), their data instances "
        "and executions, and the endpoints where each technology lives."
    ),
)

register_all()

# The portal is served from another origin in development. Origins are listed rather than
# wildcarded: "*" would also permit any site a developer happens to visit to call this API
# from their browser, and this one can trigger workflows.
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-trace-id"],
    )


@app.middleware("http")
async def trace_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """One trace_id from the edge through every layer (PRD B 5.3).

    An inbound id is honoured so the portal's id survives; otherwise one is minted. It is
    always returned, so a caller can quote it in a bug report.
    """
    tid = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = tid
    response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """Service errors carry a stable code and map to a status. The message is for
    operators and is returned only for client errors, never for 5xx."""
    body = {
        "type": "about:blank",
        "title": exc.code.replace("_", " ").title(),
        "status": exc.status,
        "code": exc.code,
        "detail": exc.message if exc.status < 500 else
                  "The request failed. Quote the trace id when reporting this.",
        "trace_id": exc.trace_id or getattr(request.state, "trace_id", None),
    }
    return JSONResponse(status_code=exc.status, content=body,
                        media_type="application/problem+json")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """A stack trace or driver error in a response body describes the schema to whoever
    provoked it. The trace id is how an operator finds the real error in the logs."""
    body = {
        "type": "about:blank",
        "title": "Internal server error",
        "status": 500,
        "code": "internal_error",
        "detail": "The request failed. Quote the trace id when reporting this.",
        "trace_id": getattr(request.state, "trace_id", None),
    }
    return JSONResponse(status_code=500, content=body, media_type="application/problem+json")


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Reports what is true, not merely that the process is up: a catalog answering 200
    with no schema makes an empty list look like an empty catalog."""
    probe = SERVICE_FACTORY.get(IHealthService).probe()
    ok = probe["database"] and probe["catalog_schema"] and probe["drift"] == 0
    return {"status": "ok" if ok else "degraded", "env": settings.env, **probe}


app.include_router(catalog_router)
app.include_router(workflow_router)
app.include_router(dataset_endpoint_router)
app.include_router(app_endpoint_router)
app.include_router(initial_data_router)
app.include_router(purpose_router)
