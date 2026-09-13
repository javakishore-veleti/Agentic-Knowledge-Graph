"""HTTP layer: bind, delegate, return (ADR-010)."""

from __future__ import annotations

import uuid

from akg_service_core import SERVICE_FACTORY
from fastapi import APIRouter, Query, Request

from ..config import settings
from ..dtos.run_dtos import (
    GetRunCtx, GetRunReq, GetRunResp, ListEnginesResp, ListRunsCtx, ListRunsReq,
    ListRunsResp, RunTasksCtx, RunTasksReq, RunTasksResp, StartRunBody, StartRunCtx,
    StartRunReq, StartRunResp,
)
from ..service.i_run_service import IRunService

router = APIRouter(prefix=settings.api_prefix, tags=["runs"])


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _svc() -> IRunService:
    return SERVICE_FACTORY.get(IRunService)


@router.post("/runs", response_model=StartRunResp)
def start_run(request: Request, body: StartRunBody) -> StartRunResp:
    """Start a workflow on whichever engine runs it.

    `started: false` with reason `already_started` is a SUCCESS: the caller sent a
    run_key it had used before, and returning the existing run is what stops a retried
    HTTP call from running a data-moving workflow twice.
    """
    ctx = StartRunCtx(
        req=StartRunReq(**body.model_dump()),
        trace_id=_tid(request), tenant_id=settings.tenant_id, env=settings.env,
    )
    return _svc().start(ctx)


# Declared before /runs/{run_id}: FastAPI matches in definition order, and a path
# parameter declared first would swallow "engines" as a run id.
@router.get("/runs/engines", response_model=ListEnginesResp)
def list_engines() -> ListEnginesResp:
    """Which engines this deployment can reach, and what each supports."""
    return _svc().engines()


@router.get("/runs", response_model=ListRunsResp)
def list_runs(
    request: Request,
    engine: str | None = None,
    workflow_ref: str | None = None,
    state: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> ListRunsResp:
    ctx = ListRunsCtx(
        req=ListRunsReq(engine=engine, workflow_ref=workflow_ref, state=state,
                        limit=limit, cursor=cursor),
        trace_id=_tid(request), tenant_id=settings.tenant_id, env=settings.env,
    )
    return _svc().list(ctx)


@router.get("/runs/{run_id}", response_model=GetRunResp)
def get_run(request: Request, run_id: uuid.UUID, refresh: bool = True) -> GetRunResp:
    ctx = GetRunCtx(
        req=GetRunReq(run_id=run_id, refresh=refresh),
        trace_id=_tid(request), tenant_id=settings.tenant_id, env=settings.env,
    )
    return _svc().get(ctx)


@router.get("/runs/{run_id}/tasks", response_model=RunTasksResp)
def run_tasks(request: Request, run_id: uuid.UUID) -> RunTasksResp:
    ctx = RunTasksCtx(
        req=RunTasksReq(run_id=run_id),
        trace_id=_tid(request), tenant_id=settings.tenant_id, env=settings.env,
    )
    return _svc().tasks(ctx)
