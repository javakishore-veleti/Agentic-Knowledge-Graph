"""HTTP layer: bind, delegate, return.

Routers build a Ctx from the request, resolve the service through SERVICE_FACTORY by
interface, and hand back the Resp. No business logic, no DAO, no ORM (ADR-010).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from ..common.object_factory import SERVICE_FACTORY
from ..config import settings
from ..dtos.catalog_dtos import (
    GetMioLineageCtx, GetMioLineageReq, GetMioLineageResp, ListAppEndpointsCtx,
    ListAppEndpointsReq, ListAppEndpointsResp, ListDataInstanceExecsCtx,
    ListDataInstanceExecsReq, ListDataInstanceExecsResp, ListDataInstancesCtx,
    ListDataInstancesReq, ListDataInstancesResp, ListDatasetsCtx, ListDatasetsReq,
    ListDatasetsResp, ListDomainsCtx, ListDomainsReq, ListDomainsResp, ListMiosCtx,
    ListMiosReq, ListMiosResp,
)
from ..service.i_catalog_service import (
    IAppEndpointService, IDataInstanceExecService, IDatasetService, IDomainService,
    IMioService,
)

router = APIRouter(prefix=settings.api_prefix, tags=["catalog"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


@router.get("/domains", response_model=ListDomainsResp)
def list_domains(
    request: Request, req: ListDomainsReq = Depends()
) -> ListDomainsResp:
    ctx = ListDomainsCtx(req=req, trace_id=_trace_id(request),
                         tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IDomainService).list_domains(ctx)


@router.get("/datasets", response_model=ListDatasetsResp)
def list_datasets(
    request: Request, req: ListDatasetsReq = Depends()
) -> ListDatasetsResp:
    ctx = ListDatasetsCtx(req=req, trace_id=_trace_id(request),
                          tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IDatasetService).list_datasets(ctx)


@router.get("/mios", response_model=ListMiosResp)
def list_mios(request: Request, req: ListMiosReq = Depends()) -> ListMiosResp:
    ctx = ListMiosCtx(req=req, trace_id=_trace_id(request),
                      tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IMioService).list_mios(ctx)


@router.get("/mios/{mio_id}/instances", response_model=ListDataInstancesResp)
def list_data_instances(
    request: Request, mio_id: uuid.UUID, kind: str | None = None, limit: int | None = None
) -> ListDataInstancesResp:
    # Path and query parameters are folded into the Req: handlers take one object, never
    # loose arguments (ADR-010).
    req = ListDataInstancesReq(mio_id=mio_id, kind=kind, limit=limit)
    ctx = ListDataInstancesCtx(req=req, trace_id=_trace_id(request),
                               tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IMioService).list_data_instances(ctx)


@router.get("/instances/{data_instance_id}/execs", response_model=ListDataInstanceExecsResp)
def list_execs(
    request: Request,
    data_instance_id: uuid.UUID,
    status: str | None = None,
    limit: int | None = None,
) -> ListDataInstanceExecsResp:
    req = ListDataInstanceExecsReq(
        data_instance_id=data_instance_id, status=status, limit=limit
    )
    ctx = ListDataInstanceExecsCtx(req=req, trace_id=_trace_id(request),
                                   tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IDataInstanceExecService).list_execs(ctx)


@router.get("/app-endpoints", response_model=ListAppEndpointsResp)
def list_app_endpoints(
    request: Request, req: ListAppEndpointsReq = Depends()
) -> ListAppEndpointsResp:
    ctx = ListAppEndpointsCtx(req=req, trace_id=_trace_id(request),
                              tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IAppEndpointService).list_app_endpoints(ctx)


@router.get("/mios/{mio_id}/lineage", response_model=GetMioLineageResp)
def get_mio_lineage(request: Request, mio_id: uuid.UUID) -> GetMioLineageResp:
    req = GetMioLineageReq(mio_id=mio_id)
    ctx = GetMioLineageCtx(req=req, trace_id=_trace_id(request),
                           tenant_id=settings.tenant_id, env=settings.env)
    return SERVICE_FACTORY.get(IMioService).get_lineage(ctx)
