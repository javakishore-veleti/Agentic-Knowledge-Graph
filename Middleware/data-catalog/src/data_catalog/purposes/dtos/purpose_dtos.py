"""Ctx / Req / Resp for purposes (ADR-010)."""

from __future__ import annotations

from dataclasses import dataclass

from akg_service_core import BaseCtx
from pydantic import BaseModel, ConfigDict, Field


class ReqDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RespDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PurposeDto(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    purpose_code: str
    name: str
    description: str
    sort_order: int
    is_active: bool
    #: Ships with the product and is referenced by shipped workflows; cannot be deleted.
    is_system: bool
    workflow_count: int = 0


class ListPurposesReq(ReqDto):
    active_only: bool = True
    q: str | None = None
    limit: int | None = None


class ListPurposesResp(RespDto):
    total: int
    items: list[PurposeDto]


@dataclass(slots=True)
class ListPurposesCtx(BaseCtx[ListPurposesReq, ListPurposesResp]):
    pass


class CreatePurposeReq(ReqDto):
    purpose_code: str = Field(min_length=2, max_length=47,
                              pattern=r"^[a-z0-9][a-z0-9_]{1,46}$")
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    sort_order: int = Field(default=500, ge=0, le=9999)


class CreatePurposeResp(RespDto):
    purpose: PurposeDto


@dataclass(slots=True)
class CreatePurposeCtx(BaseCtx[CreatePurposeReq, CreatePurposeResp]):
    pass


class UpdatePurposeReq(ReqDto):
    purpose_code: str
    name: str | None = None
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None


class UpdatePurposeResp(RespDto):
    purpose: PurposeDto


@dataclass(slots=True)
class UpdatePurposeCtx(BaseCtx[UpdatePurposeReq, UpdatePurposeResp]):
    pass


class DeletePurposeReq(ReqDto):
    purpose_code: str


class DeletePurposeResp(RespDto):
    purpose_code: str
    deleted: bool


@dataclass(slots=True)
class DeletePurposeCtx(BaseCtx[DeletePurposeReq, DeletePurposeResp]):
    pass
