"""Data management API entry point."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from akg_service_core import SERVICE_FACTORY, ServiceError
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import acquisition_router
from .bootstrap import register_all
from .config import settings
from .integration.i_clients import IAirflowClient, ICatalogClient

app = FastAPI(
    title="AKG Data Management",
    version="0.1.0",
    description=(
        "Acquires datasets from their source into a destination by triggering Airflow "
        "asynchronously. Holds no database: the catalog owns dataset state, Airflow owns "
        "execution, and the DAG reports back to the catalog itself."
    ),
)

register_all()

# Named origins, never "*": this API starts workflows, so any site a developer happens to
# visit must not be able to call it from their browser.
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
    """Reports its dependencies honestly.

    This service can answer while Airflow is down; it just cannot start anything. Saying
    so is more useful than a bare 200.
    """
    catalog_ok = SERVICE_FACTORY.get(ICatalogClient).available()
    airflow_ok = SERVICE_FACTORY.get(IAirflowClient).available()
    return {
        "status": "ok" if (catalog_ok and airflow_ok) else "degraded",
        "env": settings.env,
        "catalog": catalog_ok,
        "airflow": airflow_ok,
        "dag_id": settings.acquisition_dag_id,
    }


app.include_router(acquisition_router)
