"""Ctx / Req / Resp for every DataCatalog operation (ADR-010).

Each operation defines exactly three: `<Op>Req` holding every input, `<Op>Resp` holding
the response body, and `<Op>Ctx` which carries the Req down through service and dao and
carries the Resp back. Handlers take one Req, never loose parameters, so a new input
changes one class instead of every signature in the chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import Field

from ..common.context import BaseCtx
from .base_dtos import ItemDto, PageDto, ReqDto, RespDto

# --------------------------------------------------------------- item DTOs


class DomainDto(ItemDto):
    domain_id: uuid.UUID
    code: str
    name: str
    description: str
    created_at: datetime


class DatasetDto(ItemDto):
    dataset_id: uuid.UUID
    domain_id: uuid.UUID
    code: str
    name: str
    description: str
    source_version: str
    adapter: str
    sub_domain: str
    created_at: datetime


class MioDto(ItemDto):
    mio_id: uuid.UUID
    domain_id: uuid.UUID
    domain_code: str
    code: str
    name: str
    tech_stack: str
    state: str
    pinned_version: str | None
    documents_count: int
    edges_count: int
    size_bytes: int
    validations: dict[str, Any]
    validations_pass: bool
    dataset_count: int
    workflow_count: int
    instance_count: int
    has_cdc: bool
    generated_mio_count: int
    last_exec_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DataInstanceDto(ItemDto):
    data_instance_id: uuid.UUID
    mio_id: uuid.UUID
    kind: str
    label: str
    description: str
    state: str
    stream_cursor: str | None
    created_at: datetime
    updated_at: datetime


class DataInstanceExecDto(ItemDto):
    data_instance_exec_id: uuid.UUID
    data_instance_id: uuid.UUID
    status: str
    input_tech: str | None
    output_tech: str | None
    input_data_json: list[Any]
    output_data_json: list[Any]
    wf_execs_json: list[Any]
    produced_mio_id: uuid.UUID | None
    trace_id: str
    env: str
    requested_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AppEndpointDto(ItemDto):
    """No credential field exists here by design. secret_ref names where a secret lives;
    the secret itself never enters the catalog (ADR-009)."""

    app_endpoint_id: uuid.UUID
    code: str
    name: str
    tech_stack: str
    env: str
    host: str
    port: int | None
    database: str | None
    options: dict[str, Any]
    secret_ref: str | None
    is_active: bool


class MioLineageEdgeDto(ItemDto):
    mio_id: uuid.UUID
    code: str
    name: str
    data_instance_exec_id: uuid.UUID | None


# --------------------------------------------------------------- ListDomains


class ListDomainsReq(ReqDto):
    limit: int | None = None
    cursor: str | None = None
    q: str | None = Field(default=None, description="match code or name")


class ListDomainsResp(RespDto):
    page: PageDto
    items: list[DomainDto]


@dataclass(slots=True)
class ListDomainsCtx(BaseCtx[ListDomainsReq, ListDomainsResp]):
    pass


# --------------------------------------------------------------- ListDatasets


class ListDatasetsReq(ReqDto):
    limit: int | None = None
    cursor: str | None = None
    domain: str | None = Field(default=None, description="domain code")
    adapter: str | None = None
    q: str | None = None


class ListDatasetsResp(RespDto):
    page: PageDto
    items: list[DatasetDto]


@dataclass(slots=True)
class ListDatasetsCtx(BaseCtx[ListDatasetsReq, ListDatasetsResp]):
    pass


# --------------------------------------------------------------- ListMios


class ListMiosReq(ReqDto):
    limit: int | None = None
    cursor: str | None = None
    domain: str | None = Field(default=None, description="domain code")
    state: str | None = None
    tech_stack: str | None = None
    has_cdc: bool | None = None
    q: str | None = None


class ListMiosResp(RespDto):
    page: PageDto
    items: list[MioDto]


@dataclass(slots=True)
class ListMiosCtx(BaseCtx[ListMiosReq, ListMiosResp]):
    pass


# --------------------------------------------------------------- ListDataInstances


class ListDataInstancesReq(ReqDto):
    mio_id: uuid.UUID
    kind: str | None = Field(default=None, description="historical | realtime | cdc")
    limit: int | None = None


class ListDataInstancesResp(RespDto):
    page: PageDto
    items: list[DataInstanceDto]
    # A MIO has at most one cdc instance (ADR-009); surfaced so a caller need not scan.
    cdc_instance_id: uuid.UUID | None = None


@dataclass(slots=True)
class ListDataInstancesCtx(BaseCtx[ListDataInstancesReq, ListDataInstancesResp]):
    pass


# --------------------------------------------------------------- ListDataInstanceExecs


class ListDataInstanceExecsReq(ReqDto):
    data_instance_id: uuid.UUID
    status: str | None = None
    limit: int | None = None


class ListDataInstanceExecsResp(RespDto):
    page: PageDto
    items: list[DataInstanceExecDto]


@dataclass(slots=True)
class ListDataInstanceExecsCtx(BaseCtx[ListDataInstanceExecsReq, ListDataInstanceExecsResp]):
    pass


# --------------------------------------------------------------- ListAppEndpoints


class ListAppEndpointsReq(ReqDto):
    tech_stack: str | None = None
    env: str | None = None
    active_only: bool = True
    limit: int | None = None


class ListAppEndpointsResp(RespDto):
    page: PageDto
    items: list[AppEndpointDto]


@dataclass(slots=True)
class ListAppEndpointsCtx(BaseCtx[ListAppEndpointsReq, ListAppEndpointsResp]):
    pass


# --------------------------------------------------------------- GetMioLineage


class GetMioLineageReq(ReqDto):
    mio_id: uuid.UUID


class GetMioLineageResp(RespDto):
    mio_id: uuid.UUID
    produced_from: list[MioLineageEdgeDto]
    generated: list[MioLineageEdgeDto]


@dataclass(slots=True)
class GetMioLineageCtx(BaseCtx[GetMioLineageReq, GetMioLineageResp]):
    pass
