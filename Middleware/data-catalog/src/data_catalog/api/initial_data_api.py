"""Administration: first-run data loading (ADR-017)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from ..common.object_factory import SERVICE_FACTORY
from ..config import settings
from ..service.i_initial_data_service import IInitialDataService

router = APIRouter(prefix=f"{settings.api_prefix}/admin", tags=["administration"])


class LoadReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Re-run a load that already succeeded. Without it, a second press does nothing.
    force: bool = False


class SeedStatusReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    inserted: int = 0
    skipped: int = 0
    error: dict[str, Any] | None = None
    wf_ref_id: str | None = None


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _svc() -> IInitialDataService:
    return SERVICE_FACTORY.get(IInitialDataService)


@router.get("/initial-data")
def status(request: Request) -> dict[str, Any]:
    """Row counts, last run and prerequisites, in load order."""
    return {"items": _svc().status(settings.tenant_id)}


@router.post("/initial-data/{entity}/load")
def load(request: Request, entity: str, body: LoadReq | None = None) -> dict[str, Any]:
    """Load one entity's reference content.

    A refusal is a 200 with `claimed: false` and a reason -- `already_loaded`,
    `already_running`, or `requires_<entity>`. Pressing the button twice is an expected
    thing to do, not an error to raise.
    """
    return _svc().load(
        entity, settings.tenant_id, settings.env, _tid(request),
        requested_by=request.headers.get("x-requested-by"),
        force=(body or LoadReq()).force,
    )


@router.post("/initial-data/{tracker_id}/status")
def report(request: Request, tracker_id: uuid.UUID, body: SeedStatusReq) -> dict[str, Any]:
    """Called by the seeding DAG when a run ends.

    Unauthenticated for the same reason as the acquisition callback, and with the same
    caveat: before this is reachable beyond the local network it needs service-to-service
    auth.
    """
    return _svc().report(
        tracker_id, body.status, body.inserted, body.skipped, body.error, body.wf_ref_id
    )
