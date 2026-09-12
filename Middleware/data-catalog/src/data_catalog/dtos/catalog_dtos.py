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


# ================================================================ workflow master


class WorkflowParamDto(ItemDto):
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    default: Any | None = None
    options: list[str] | None = None
    help: str | None = None


class WorkflowDto(ItemDto):
    workflow_id: uuid.UUID
    code: str
    name: str
    description: str
    domain: str
    sub_domain: str
    default_tech_stack: str
    purpose: str
    params_json: list[WorkflowParamDto]
    is_active: bool


class MioWorkflowDto(ItemDto):
    """A workflow attached to a MIO, joined to the master so the portal gets the
    parameter definitions in the same read."""

    workflow_id: uuid.UUID | None
    workflow_code: str
    workflow_name: str | None
    description: str | None
    default_tech_stack: str | None
    purpose: str
    enabled: bool
    params_json: list[WorkflowParamDto] = []
    param_overrides_json: dict[str, Any] = {}
    #: False when the association points at a missing or deactivated workflow. The portal
    #: must not offer a trigger button for one of these.
    workflow_active: bool = False


class ListWorkflowsReq(ReqDto):
    limit: int | None = None
    cursor: str | None = None
    domain: str | None = None
    active_only: bool = True
    q: str | None = None


class ListWorkflowsResp(RespDto):
    page: PageDto
    items: list[WorkflowDto]


@dataclass(slots=True)
class ListWorkflowsCtx(BaseCtx[ListWorkflowsReq, ListWorkflowsResp]):
    pass


# ================================================================ MIO CRUD


class CreateMioReq(ReqDto):
    domain_code: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=127)
    name: str = Field(min_length=1)
    description: str = ""
    tech_stack: str = Field(min_length=1)
    dataset_ids: list[uuid.UUID] = []


class CreateMioResp(RespDto):
    mio: MioDto


@dataclass(slots=True)
class CreateMioCtx(BaseCtx[CreateMioReq, CreateMioResp]):
    pass


class UpdateMioReq(ReqDto):
    mio_id: uuid.UUID
    name: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    state: str | None = None
    pinned_version: str | None = None


class UpdateMioResp(RespDto):
    mio: MioDto


@dataclass(slots=True)
class UpdateMioCtx(BaseCtx[UpdateMioReq, UpdateMioResp]):
    pass


class DeleteMioReq(ReqDto):
    mio_id: uuid.UUID


class DeleteMioResp(RespDto):
    mio_id: uuid.UUID
    deleted: bool


@dataclass(slots=True)
class DeleteMioCtx(BaseCtx[DeleteMioReq, DeleteMioResp]):
    pass


# ================================================================ MIO <-> workflow


class ListMioWorkflowsReq(ReqDto):
    mio_id: uuid.UUID


class ListMioWorkflowsResp(RespDto):
    mio_id: uuid.UUID
    items: list[MioWorkflowDto]


@dataclass(slots=True)
class ListMioWorkflowsCtx(BaseCtx[ListMioWorkflowsReq, ListMioWorkflowsResp]):
    pass


class AttachWorkflowReq(ReqDto):
    mio_id: uuid.UUID
    workflow_id: uuid.UUID
    purpose: str = "build"
    param_overrides: dict[str, Any] = {}


class AttachWorkflowResp(RespDto):
    mio_id: uuid.UUID
    workflow_id: uuid.UUID
    attached: bool


@dataclass(slots=True)
class AttachWorkflowCtx(BaseCtx[AttachWorkflowReq, AttachWorkflowResp]):
    pass


class DetachWorkflowReq(ReqDto):
    mio_id: uuid.UUID
    workflow_id: uuid.UUID


class DetachWorkflowResp(RespDto):
    mio_id: uuid.UUID
    workflow_id: uuid.UUID
    detached: bool


@dataclass(slots=True)
class DetachWorkflowCtx(BaseCtx[DetachWorkflowReq, DetachWorkflowResp]):
    pass


# ================================================================ invoke


class InvokeMioWorkflowReq(ReqDto):
    mio_id: uuid.UUID
    workflow_id: uuid.UUID
    input_data: dict[str, Any] = {}
    idempotency_key: str | None = None


class InvokeMioWorkflowResp(RespDto):
    """The catalog records the execution and hands the engine choice to the orchestrator.

    `wf_ref_id` is absent until the engine accepts the submission, which is what makes a
    failed submit visible rather than silent (ADR-008).
    """

    mio_id: uuid.UUID
    workflow_id: uuid.UUID
    data_instance_exec_id: uuid.UUID
    status: str
    wf_ref_id: str | None = None


@dataclass(slots=True)
class InvokeMioWorkflowCtx(BaseCtx[InvokeMioWorkflowReq, InvokeMioWorkflowResp]):
    pass


# ================================================================ dataset locations


class DatasetEndpointDto(ItemDto):
    """Where a dataset came from, or where a copy of it is stored (ADR-012).

    `uri` carries no credentials -- a database CHECK rejects userinfo before the host, and
    the connection secret stays on the app_endpoint's secret_ref.
    """

    dataset_endpoint_id: uuid.UUID
    dataset_id: uuid.UUID
    role: str
    #: Null only for an external source: nobody registers Kaggle as an app endpoint.
    app_endpoint_id: uuid.UUID | None
    location_kind: str
    uri: str
    options: dict[str, Any]
    format: str | None
    bytes: int
    object_count: int
    state: str
    is_primary: bool
    last_synced_at: datetime | None


class DatasetOverviewDto(ItemDto):
    """A dataset with its locations resolved, for the list API."""

    dataset_id: uuid.UUID
    domain_id: uuid.UUID
    domain_code: str
    code: str
    name: str
    description: str
    source_version: str
    adapter: str
    sub_domain: str
    created_at: datetime
    location_count: int
    source_uri: str | None
    source_kind: str | None
    stored_bytes: int
    #: False means nobody can rebuild this dataset: no source location was recorded.
    has_source: bool
    has_available_copy: bool


class ListDatasetEndpointsReq(ReqDto):
    dataset_id: uuid.UUID
    role: str | None = None


class ListDatasetEndpointsResp(RespDto):
    dataset_id: uuid.UUID
    items: list[DatasetEndpointDto]


@dataclass(slots=True)
class ListDatasetEndpointsCtx(BaseCtx[ListDatasetEndpointsReq, ListDatasetEndpointsResp]):
    pass


class AddDatasetEndpointReq(ReqDto):
    dataset_id: uuid.UUID
    role: str = "landing"
    app_endpoint_id: uuid.UUID | None = None
    location_kind: str
    uri: str = Field(min_length=3)
    options: dict[str, Any] = {}
    format: str | None = None
    is_primary: bool = False


class AddDatasetEndpointResp(RespDto):
    dataset_endpoint_id: uuid.UUID


@dataclass(slots=True)
class AddDatasetEndpointCtx(BaseCtx[AddDatasetEndpointReq, AddDatasetEndpointResp]):
    pass
