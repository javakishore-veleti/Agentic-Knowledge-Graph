"""Dataset locations, the acquisition claim, and the Airflow callback (ADR-012, ADR-013).

Thin by rule: bind, delegate, return. No SQL, no DAO, no business rules — an earlier
version of this file reached straight into the DAO and the database, and the layering test
caught it.

SECURITY: the callback mutates dataset state from outside this service and is
unauthenticated, because nothing in the stack authenticates yet. Before it is reachable
beyond the local network it needs the gateway's service-to-service auth or a shared secret
Airflow presents — an open endpoint that can mark data "available" is an open endpoint that
can make a build read nothing.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from ..common.object_factory import SERVICE_FACTORY
from ..config import settings
from ..dtos.catalog_dtos import AddDatasetEndpointReq
from ..service.i_dataset_location_service import IDatasetLocationService

router = APIRouter(prefix=settings.api_prefix, tags=["dataset-locations"])


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _svc() -> IDatasetLocationService:
    return SERVICE_FACTORY.get(IDatasetLocationService)


class ClaimReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exec_id: uuid.UUID
    force: bool = False


class ClaimResp(BaseModel):
    claimed: bool
    reason: str


class SyncStatusReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    bytes: int | None = None
    object_count: int | None = None
    error: dict[str, Any] | None = None
    wf_ref_id: str | None = None


@router.get("/datasets/{dataset_id}/endpoints")
def list_dataset_endpoints(
    request: Request, dataset_id: uuid.UUID, role: str | None = None
) -> dict[str, Any]:
    items = _svc().list_locations(settings.tenant_id, dataset_id, role, _tid(request))
    return {"dataset_id": str(dataset_id),
            "items": [i.model_dump(mode="json") for i in items]}


@router.post("/datasets/{dataset_id}/endpoints", status_code=201)
def add_dataset_endpoint(
    request: Request, dataset_id: uuid.UUID, body: AddDatasetEndpointReq
) -> dict[str, Any]:
    req = body.model_copy(update={"dataset_id": dataset_id})
    new_id = _svc().add_location(settings.tenant_id, req, _tid(request))
    return {"dataset_endpoint_id": str(new_id)}


@router.get("/dataset-endpoints/stuck")
def stuck_syncs() -> dict[str, Any]:
    """Endpoints claimed by a run that never reported back.

    Declared before the /{id} route deliberately: FastAPI matches in definition order, and
    a path-parameter route declared first would swallow "stuck" as an id.
    """
    return {"items": _svc().stuck(settings.tenant_id)}


@router.get("/dataset-endpoints/{dataset_endpoint_id}")
def get_dataset_endpoint(dataset_endpoint_id: uuid.UUID) -> dict[str, Any]:
    return _svc().get_location(settings.tenant_id, dataset_endpoint_id) or {}


@router.post("/dataset-endpoints/{dataset_endpoint_id}/claim", response_model=ClaimResp)
def claim(request: Request, dataset_endpoint_id: uuid.UUID, body: ClaimReq) -> ClaimResp:
    """Claim this endpoint for acquisition, or refuse and say why.

    Refusal is a normal outcome: `already_available` means the data is there and
    re-downloading it would be waste, which is the whole point of asking first.
    """
    claimed, reason = _svc().claim(
        settings.tenant_id, dataset_endpoint_id, body.exec_id, body.force, _tid(request)
    )
    return ClaimResp(claimed=claimed, reason=reason)


@router.post("/dataset-endpoints/{dataset_endpoint_id}/sync-status")
def sync_status(
    request: Request, dataset_endpoint_id: uuid.UUID, body: SyncStatusReq
) -> dict[str, Any]:
    """Called by the Airflow DAG when a run ends.

    Availability is derived from what the run reports, not asserted by it: a COMPLETED run
    that moved zero bytes leaves the endpoint unavailable, because the run finishing and
    the data arriving are different facts.
    """
    out = _svc().report_sync(
        settings.tenant_id, dataset_endpoint_id, body.status, body.bytes,
        body.object_count, body.error, body.wf_ref_id, _tid(request),
    )
    return {"updated": out is not None, **(out or {})}
