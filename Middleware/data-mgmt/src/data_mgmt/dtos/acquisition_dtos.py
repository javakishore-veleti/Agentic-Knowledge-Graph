"""Ctx / Req / Resp for acquisition (ADR-010, ADR-013)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from akg_service_core import BaseCtx
from pydantic import BaseModel, ConfigDict, Field


class ReqDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RespDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AcquireDatasetBody(ReqDto):
    """What a CLIENT may send.

    Deliberately without dataset_endpoint_id: that is in the path, and `extra="forbid"`
    meant a caller posting only {"force": false} -- the obvious thing to send -- got a
    422 naming a field it had no business repeating.
    """

    force: bool = False
    params: dict[str, Any] = {}


class AcquireDatasetReq(ReqDto):
    dataset_endpoint_id: uuid.UUID
    #: Re-acquire data that is already available. Without this an available endpoint is
    #: left alone, which is the whole point: we do not re-download what we have.
    force: bool = False
    params: dict[str, Any] = {}


class AcquireDatasetResp(RespDto):
    dataset_endpoint_id: uuid.UUID
    #: False when nothing was started. `reason` says why, and that is a normal outcome,
    #: not an error: "already_available" is the success case for an idempotent caller.
    started: bool
    reason: str
    exec_id: uuid.UUID | None = None
    dag_run_id: str | None = None
    state: str | None = None
    sync_wf_status: str | None = None


@dataclass(slots=True)
class AcquireDatasetCtx(BaseCtx[AcquireDatasetReq, AcquireDatasetResp]):
    pass


class AcquisitionStatusReq(ReqDto):
    dataset_endpoint_id: uuid.UUID


class AcquisitionStatusResp(RespDto):
    dataset_endpoint_id: uuid.UUID
    state: str
    sync_wf_status: str | None
    sync_started_at: str | None
    sync_finished_at: str | None
    bytes: int
    sync_attempts: int
    dag_run_state: str | None = None


@dataclass(slots=True)
class AcquisitionStatusCtx(BaseCtx[AcquisitionStatusReq, AcquisitionStatusResp]):
    pass
