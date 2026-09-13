"""The engine-neutral contract.

Nothing here names a DAG, a state machine or a job. That is the whole point: a caller
asks for a workflow to run and reads back one vocabulary of states, whichever engine
actually ran it. Engine-specific identifiers survive only as `engine_run_id`, which is
opaque to callers and meaningful to the adapter that produced it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from akg_service_core import BaseCtx
from pydantic import BaseModel, ConfigDict, Field


class ReqDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RespDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


#: One vocabulary for every engine. Adapters map their own states onto these and callers
#: never learn the difference -- an Airflow "queued" and a Step Functions "PENDING" are
#: the same fact about the work.
RUN_STATES = ("queued", "running", "succeeded", "failed", "cancelled")

#: Terminal states. A run in one of these will not change again, which is what lets a
#: poller stop and a claim be released.
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


class StartRunBody(ReqDto):
    """What a caller sends. No run identity: the service assigns that."""

    #: Which engine should run it. 'airflow' today; the rest answer 501 rather than
    #: pretending, so a caller learns the truth at the call instead of at the timeout.
    engine: str = "airflow"

    #: What to run, in the engine's own terms -- a dag_id, a state machine ARN, a job
    #: name. The orchestrator does not interpret it; the adapter does.
    workflow_ref: str

    #: The caller's idempotency key. Two requests carrying the same key return the SAME
    #: run rather than starting a second one: a retried HTTP call must not double-run a
    #: workflow that moves data.
    run_key: str | None = None

    conf: dict[str, Any] = Field(default_factory=dict)

    #: Free-form, stored and returned untouched. Callers use it to tie a run back to the
    #: thing that caused it (a dataset endpoint, a MIO) without the orchestrator needing
    #: to know what any of those are.
    caller_ref: dict[str, Any] = Field(default_factory=dict)


class StartRunReq(ReqDto):
    engine: str
    workflow_ref: str
    run_key: str | None = None
    conf: dict[str, Any] = Field(default_factory=dict)
    caller_ref: dict[str, Any] = Field(default_factory=dict)


class RunDto(RespDto):
    run_id: uuid.UUID
    engine: str
    workflow_ref: str
    engine_run_id: str | None
    run_key: str | None
    state: str
    #: What the engine itself called the state, kept for operators reading a trace. The
    #: normalised `state` is what code should branch on.
    engine_state: str | None = None
    conf: dict[str, Any] = Field(default_factory=dict)
    caller_ref: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    trace_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class StartRunResp(RespDto):
    run: RunDto
    #: False when an existing run was returned instead of a new one being started.
    #: A success, not an error: that is what the idempotency key is for.
    started: bool
    reason: str


class GetRunReq(ReqDto):
    run_id: uuid.UUID
    #: Ask the engine rather than trusting the stored row. Off by default so a listing
    #: does not fan out into one engine call per row.
    refresh: bool = True


class GetRunResp(RespDto):
    run: RunDto


class ListRunsReq(ReqDto):
    engine: str | None = None
    workflow_ref: str | None = None
    state: str | None = None
    limit: int = 50
    cursor: str | None = None


class ListRunsResp(RespDto):
    items: list[RunDto]
    next_cursor: str | None = None


class RunTaskDto(RespDto):
    task_id: str
    state: str
    engine_state: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    try_number: int | None = None


class RunTasksReq(ReqDto):
    run_id: uuid.UUID


class RunTasksResp(RespDto):
    run_id: uuid.UUID
    items: list[RunTaskDto]


class EngineDto(RespDto):
    engine: str
    available: bool
    #: What this adapter can actually do. A caller that needs task-level detail can ask
    #: rather than discovering a 501 halfway through a screen.
    supports_tasks: bool
    supports_cancel: bool
    detail: str | None = None


class ListEnginesResp(RespDto):
    items: list[EngineDto]


@dataclass(slots=True)
class StartRunCtx(BaseCtx[StartRunReq, StartRunResp]):
    pass


@dataclass(slots=True)
class GetRunCtx(BaseCtx[GetRunReq, GetRunResp]):
    pass


@dataclass(slots=True)
class ListRunsCtx(BaseCtx[ListRunsReq, ListRunsResp]):
    pass


@dataclass(slots=True)
class RunTasksCtx(BaseCtx[RunTasksReq, RunTasksResp]):
    pass
