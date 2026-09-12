"""Purpose CRUD. Thin by rule: bind, delegate, return (ADR-010)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from ...common.object_factory import SERVICE_FACTORY
from ...config import settings
from ..dtos.purpose_dtos import (
    CreatePurposeCtx, CreatePurposeReq, CreatePurposeResp, DeletePurposeCtx,
    DeletePurposeReq, DeletePurposeResp, ListPurposesCtx, ListPurposesReq,
    ListPurposesResp, UpdatePurposeCtx, UpdatePurposeReq, UpdatePurposeResp,
)
from ..service.i_purpose_service import IPurposeService

router = APIRouter(prefix=f"{settings.api_prefix}/purposes", tags=["purposes"])


def _ctx(kind, req, request: Request):
    return kind(req=req,
                trace_id=getattr(request.state, "trace_id", str(uuid.uuid4())),
                tenant_id=settings.tenant_id, env=settings.env)


def _svc() -> IPurposeService:
    return SERVICE_FACTORY.get(IPurposeService)


@router.get("", response_model=ListPurposesResp)
def list_purposes(request: Request, req: ListPurposesReq = Depends()) -> ListPurposesResp:
    return _svc().list(_ctx(ListPurposesCtx, req, request))


@router.post("", response_model=CreatePurposeResp, status_code=201)
def create_purpose(request: Request, body: CreatePurposeReq) -> CreatePurposeResp:
    return _svc().create(_ctx(CreatePurposeCtx, body, request))


@router.patch("/{purpose_code}", response_model=UpdatePurposeResp)
def update_purpose(
    request: Request, purpose_code: str, body: UpdatePurposeReq
) -> UpdatePurposeResp:
    # The path wins over the body: a mismatched code in a payload must not edit a
    # different row than the URL names.
    req = body.model_copy(update={"purpose_code": purpose_code})
    return _svc().update(_ctx(UpdatePurposeCtx, req, request))


@router.delete("/{purpose_code}", response_model=DeletePurposeResp)
def delete_purpose(request: Request, purpose_code: str) -> DeletePurposeResp:
    req = DeletePurposeReq(purpose_code=purpose_code)
    return _svc().delete(_ctx(DeletePurposeCtx, req, request))
