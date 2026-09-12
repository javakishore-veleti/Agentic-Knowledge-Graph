"""Request-scoped context.

The Ctx is what travels api -> service -> dao. It carries the Req, the cross-cutting
fields, the task trail, and finally the Resp. Nothing framework-specific goes on it: no
session, no Request, no connection. Those live inside the DAO implementation, because a
Ctx is a DTO and a DTO with a live database handle on it stops being one (ADR-010).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

REQ = TypeVar("REQ")
RESP = TypeVar("RESP")


@dataclass(slots=True)
class TaskRecord:
    """One intermediary task's outcome, kept so a slow or failing step is attributable."""

    name: str
    started_at: datetime
    finished_at: datetime | None = None
    skipped: bool = False
    error: str | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds() * 1000.0


@dataclass(slots=True)
class BaseCtx(Generic[REQ, RESP]):
    req: REQ
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "reference"
    env: str = "local"
    requested_by: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Filled in by the service's tasks. Optional until the workflow completes, which is
    # why every read of it is guarded rather than assumed.
    resp: RESP | None = None

    # Scratch space shared between tasks of one workflow. Tasks communicate through this
    # rather than by returning values, so the workflow runner stays uniform.
    scratch: dict[str, Any] = field(default_factory=dict)
    tasks: list[TaskRecord] = field(default_factory=list)

    def require_resp(self) -> RESP:
        """A workflow that finished without producing a response is a bug in the
        workflow, not a None for the caller to handle."""
        if self.resp is None:
            raise RuntimeError(
                f"workflow completed without setting resp (trace_id={self.trace_id}); "
                f"tasks run: {[t.name for t in self.tasks]}"
            )
        return self.resp

    @property
    def failed_task(self) -> TaskRecord | None:
        return next((t for t in self.tasks if t.error), None)
