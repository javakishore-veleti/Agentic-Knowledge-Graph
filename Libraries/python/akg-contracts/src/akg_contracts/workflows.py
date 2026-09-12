"""Workflow trigger and execution-log contracts (ADR-008).

The Admin portal speaks these types and never names an engine. `tech_stack` says which
engine ran a given execution; the caller does not choose it, configuration does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Env, TechStack, WorkflowStatus
from .ids import TenantId, TraceId


class WorkflowTrigger(BaseModel):
    """What the Admin portal sends. Deliberately engine-free."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1, max_length=64)
    sub_domain: str = Field(min_length=1, max_length=64)
    workflow: str = Field(min_length=1, max_length=128)
    input_data: dict[str, Any] = Field(default_factory=dict)
    # Lets a double-clicked button collapse to one execution rather than two.
    idempotency_key: str | None = Field(default=None, max_length=128)


class WorkflowExecution(BaseModel):
    """One row of workflow_exec_log."""

    model_config = ConfigDict(extra="forbid")

    exec_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Optional parent batch. An ad-hoc Admin run has none; a 1,334-file ingest has one
    # batch and 1,334 of these.
    wf_batch_id: str | None = None
    domain: str
    sub_domain: str
    workflow: str
    tech_stack: TechStack
    # The engine's own id: Airflow dag_run_id, Step Functions execution ARN, Lambda
    # request id. None until the engine has accepted the submission.
    wf_ref_id: str | None = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    trace_id: TraceId
    tenant_id: TenantId
    env: Env
    requested_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def engine_id_present_once_submitted(self) -> WorkflowExecution:
        if self.status is not WorkflowStatus.PENDING and self.wf_ref_id is None:
            raise ValueError(f"status {self.status} requires wf_ref_id from the engine")
        return self

    @model_validator(mode="after")
    def terminal_states_are_finished(self) -> WorkflowExecution:
        if self.status.terminal and self.finished_at is None:
            raise ValueError(f"terminal status {self.status} requires finished_at")
        if not self.status.terminal and self.finished_at is not None:
            raise ValueError(f"non-terminal status {self.status} cannot have finished_at")
        return self

    @model_validator(mode="after")
    def failure_carries_a_reason(self) -> WorkflowExecution:
        if self.status is WorkflowStatus.FAILED and not self.error:
            raise ValueError("FAILED requires error details")
        return self


class WorkflowBatch(BaseModel):
    """One instance of a batch execution: the header over many WorkflowExecution rows.

    The counters are a cache so the Admin portal can page a batch list without aggregating
    millions of detail rows. They are recounted against the detail table by the
    wf_batch_drift view -- a counter nobody checks is a counter that drifts.
    """

    model_config = ConfigDict(extra="forbid")

    wf_batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_name: str = Field(min_length=1, max_length=128)
    batch_instance: str = Field(min_length=1, max_length=128)
    domain: str
    sub_domain: str
    tech_stack: TechStack
    status: WorkflowStatus = WorkflowStatus.PENDING
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    total_count: int = Field(default=0, ge=0)
    succeeded_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    trace_id: TraceId
    tenant_id: TenantId
    env: Env
    requested_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def counts_do_not_exceed_total(self) -> "WorkflowBatch":
        if self.succeeded_count + self.failed_count > self.total_count:
            raise ValueError(
                f"succeeded+failed ({self.succeeded_count + self.failed_count}) "
                f"exceeds total_count ({self.total_count})"
            )
        return self

    @model_validator(mode="after")
    def terminal_batches_are_finished(self) -> "WorkflowBatch":
        if self.status.terminal and self.finished_at is None:
            raise ValueError(f"terminal status {self.status} requires finished_at")
        return self

    @property
    def open_count(self) -> int:
        return self.total_count - self.succeeded_count - self.failed_count
