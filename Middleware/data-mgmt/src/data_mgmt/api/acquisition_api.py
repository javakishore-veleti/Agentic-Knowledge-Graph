"""HTTP layer: bind, delegate, return (ADR-010)."""

from __future__ import annotations

import uuid

from akg_service_core import SERVICE_FACTORY
from fastapi import APIRouter, Request

from ..config import settings
from ..dtos.acquisition_dtos import (
    AcquireDatasetBody, AcquireDatasetCtx, AcquireDatasetReq, AcquireDatasetResp,
    AcquisitionStatusCtx,
    AcquisitionStatusReq, AcquisitionStatusResp,
)
from ..service.i_acquisition_service import IAcquisitionService

router = APIRouter(prefix=settings.api_prefix, tags=["acquisition"])


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


@router.post("/dataset-endpoints/{dataset_endpoint_id}/acquire",
             response_model=AcquireDatasetResp)
def acquire(
    request: Request, dataset_endpoint_id: uuid.UUID,
    body: AcquireDatasetBody | None = None,
) -> AcquireDatasetResp:
    """Acquire a dataset from its source into this destination.

    Idempotent by design: if the destination already holds the data, nothing is started
    and `started` is false with reason `already_available`. That is a success, not an
    error, so it stays a 200 -- a caller that retries should not have to parse a failure
    to learn that its data is already there.
    """
    # The path owns the identity; the body only carries options. Building the Req here
    # rather than accepting one keeps a caller from naming a different endpoint in the
    # body than the one it addressed.
    opts = body or AcquireDatasetBody()
    req = AcquireDatasetReq(
        dataset_endpoint_id=dataset_endpoint_id, force=opts.force, params=opts.params,
    )
    ctx = AcquireDatasetCtx(req=req, trace_id=_tid(request),
                            tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IAcquisitionService).acquire(ctx)


@router.get("/dataset-endpoints/{dataset_endpoint_id}/acquisition",
            response_model=AcquisitionStatusResp)
def status(request: Request, dataset_endpoint_id: uuid.UUID) -> AcquisitionStatusResp:
    req = AcquisitionStatusReq(dataset_endpoint_id=dataset_endpoint_id)
    ctx = AcquisitionStatusCtx(req=req, trace_id=_tid(request),
                               tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IAcquisitionService).status(ctx)
