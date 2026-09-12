"""API response models.

`extra="forbid"` on the way in; explicit field lists on the way out. AppEndpointOut in
particular has no field that can carry a credential, so a secret added to the table by
some future writer still cannot reach a client through this API (ADR-009).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["historical", "realtime", "cdc"]
ExecStatus = Literal["PENDING", "SUBMITTED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
MioState = Literal["draft", "building", "ready", "live", "rejected", "retired"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DomainOut(Out):
    domain_id: uuid.UUID
    code: str
    name: str
    description: str
    created_at: datetime


class DatasetOut(Out):
    dataset_id: uuid.UUID
    domain_id: uuid.UUID
    code: str
    name: str
    description: str
    source_version: str
    adapter: str
    sub_domain: str
    created_at: datetime


class MioOut(Out):
    """One row of catalog.mio_overview."""

    mio_id: uuid.UUID
    domain_id: uuid.UUID
    domain_code: str
    code: str
    name: str
    tech_stack: str
    state: MioState
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


class DataInstanceOut(Out):
    data_instance_id: uuid.UUID
    mio_id: uuid.UUID
    kind: Kind
    label: str
    description: str
    state: str
    # Only ever set on a cdc instance, by database constraint.
    stream_cursor: str | None
    created_at: datetime
    updated_at: datetime


class DataInstanceExecOut(Out):
    data_instance_exec_id: uuid.UUID
    data_instance_id: uuid.UUID
    status: ExecStatus
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


class AppEndpointOut(Out):
    """Deliberately omits secret_ref's *value* and has no credential field at all.

    secret_ref is a Key Vault pointer and is safe to expose -- it names where a secret
    lives, not what it is -- but there is no `password`, `token` or `connection_string`
    field here by design, so this response cannot become a credential leak.
    """

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


class Page(BaseModel):
    """Opaque-cursor pagination (PRD A 11.1). Offsets shift under concurrent inserts."""

    total: int
    limit: int
    next_cursor: str | None = None


class DomainList(BaseModel):
    page: Page
    items: list[DomainOut]


class DatasetList(BaseModel):
    page: Page
    items: list[DatasetOut]


class MioList(BaseModel):
    page: Page
    items: list[MioOut]


class DataInstanceList(BaseModel):
    page: Page
    items: list[DataInstanceOut]


class ExecList(BaseModel):
    page: Page
    items: list[DataInstanceExecOut]


class AppEndpointList(BaseModel):
    page: Page
    items: list[AppEndpointOut]


class Problem(BaseModel):
    """RFC 9457 Problem Details (PRD A 11.1)."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str | None = None
    trace_id: str | None = None


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    env: str
    database: bool
    catalog_schema: bool
    drift: int = Field(
        description="rows where wf_execs_json disagrees with wf_exec_log; non-zero is a bug"
    )
