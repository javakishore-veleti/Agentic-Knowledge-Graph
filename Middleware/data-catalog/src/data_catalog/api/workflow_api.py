"""Workflow master, MIO CRUD, association and invocation (ADR-010)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from ..common.object_factory import SERVICE_FACTORY
from ..config import settings
from ..dtos.catalog_dtos import (
    AttachWorkflowCtx, AttachWorkflowReq, AttachWorkflowResp, CreateMioCtx, CreateMioReq,
    CreateMioResp, DeleteMioCtx, DeleteMioReq, DeleteMioResp, DetachWorkflowCtx,
    DetachWorkflowReq, DetachWorkflowResp, InvokeMioWorkflowCtx, InvokeMioWorkflowReq,
    InvokeMioWorkflowResp, ListMioWorkflowsCtx, ListMioWorkflowsReq, ListMioWorkflowsResp,
    ListWorkflowsCtx, ListWorkflowsReq, ListWorkflowsResp, UpdateMioCtx, UpdateMioReq,
    UpdateMioResp,
)
from ..service.i_catalog_service import IMioWriteService, IWorkflowService

router = APIRouter(prefix=settings.api_prefix, tags=["workflows"])


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _ctx(kind, req, request: Request):
    return kind(req=req, trace_id=_tid(request), tenant_id=settings.tenant_id,
                env=settings.env)


@router.get("/workflows", response_model=ListWorkflowsResp)
def list_workflows(request: Request, req: ListWorkflowsReq = Depends()) -> ListWorkflowsResp:
    return SERVICE_FACTORY.get(IWorkflowService).list_workflows(
        _ctx(ListWorkflowsCtx, req, request)
    )


@router.get("/mios/{mio_id}/workflows", response_model=ListMioWorkflowsResp)
def list_mio_workflows(request: Request, mio_id: uuid.UUID) -> ListMioWorkflowsResp:
    req = ListMioWorkflowsReq(mio_id=mio_id)
    return SERVICE_FACTORY.get(IWorkflowService).list_mio_workflows(
        _ctx(ListMioWorkflowsCtx, req, request)
    )


@router.post("/mios/{mio_id}/workflows", response_model=AttachWorkflowResp)
def attach_workflow(
    request: Request, mio_id: uuid.UUID, body: AttachWorkflowReq
) -> AttachWorkflowResp:
    # The path is authoritative over the body: a mismatched id in a payload must not
    # silently attach a workflow to a different MIO.
    req = body.model_copy(update={"mio_id": mio_id})
    return SERVICE_FACTORY.get(IWorkflowService).attach_workflow(
        _ctx(AttachWorkflowCtx, req, request)
    )


@router.delete("/mios/{mio_id}/workflows/{workflow_id}", response_model=DetachWorkflowResp)
def detach_workflow(
    request: Request, mio_id: uuid.UUID, workflow_id: uuid.UUID
) -> DetachWorkflowResp:
    req = DetachWorkflowReq(mio_id=mio_id, workflow_id=workflow_id)
    return SERVICE_FACTORY.get(IWorkflowService).detach_workflow(
        _ctx(DetachWorkflowCtx, req, request)
    )


@router.post("/mios/{mio_id}/workflows/{workflow_id}/invoke",
             response_model=InvokeMioWorkflowResp)
def invoke_workflow(
    request: Request, mio_id: uuid.UUID, workflow_id: uuid.UUID,
    body: InvokeMioWorkflowReq,
) -> InvokeMioWorkflowResp:
    req = body.model_copy(update={"mio_id": mio_id, "workflow_id": workflow_id})
    return SERVICE_FACTORY.get(IWorkflowService).invoke(
        _ctx(InvokeMioWorkflowCtx, req, request)
    )


@router.post("/mios", response_model=CreateMioResp, status_code=201)
def create_mio(request: Request, body: CreateMioReq) -> CreateMioResp:
    return SERVICE_FACTORY.get(IMioWriteService).create_mio(
        _ctx(CreateMioCtx, body, request)
    )


@router.patch("/mios/{mio_id}", response_model=UpdateMioResp)
def update_mio(request: Request, mio_id: uuid.UUID, body: UpdateMioReq) -> UpdateMioResp:
    req = body.model_copy(update={"mio_id": mio_id})
    return SERVICE_FACTORY.get(IMioWriteService).update_mio(
        _ctx(UpdateMioCtx, req, request)
    )


@router.delete("/mios/{mio_id}", response_model=DeleteMioResp)
def delete_mio(request: Request, mio_id: uuid.UUID) -> DeleteMioResp:
    req = DeleteMioReq(mio_id=mio_id)
    return SERVICE_FACTORY.get(IMioWriteService).delete_mio(
        _ctx(DeleteMioCtx, req, request)
    )
