"""The orchestration port.

Every engine looks like this to the rest of the service. Adding Step Functions means
adding one class here, not touching a caller -- which is the reason this service exists:
Airflow's auth scheme and URL layout had already leaked into data-mgmt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, NamedTuple


class EngineRun(NamedTuple):
    engine_run_id: str | None
    state: str
    engine_state: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: dict[str, Any] | None = None


class EngineTask(NamedTuple):
    task_id: str
    state: str
    engine_state: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    try_number: int | None = None


class EngineError(RuntimeError):
    """The engine refused or could not be reached.

    Carries the reason so a caller sees "airflow: 403 from the REST API" instead of
    "unavailable" -- the distinction that cost a long debugging session when a healthy
    Airflow with the wrong auth backend was indistinguishable from a stopped one.
    """

    def __init__(self, engine: str, reason: str, status: int | None = None) -> None:
        super().__init__(f"{engine}: {reason}")
        self.engine = engine
        self.reason = reason
        self.status = status


class IEngineAdapter(ABC):
    """One workflow engine, behind one contract."""

    #: Stable name callers pass as `engine`.
    name: str = ""
    supports_tasks: bool = False
    supports_cancel: bool = False

    @abstractmethod
    def start(self, workflow_ref: str, run_id: str, conf: dict[str, Any],
              trace_id: str) -> EngineRun:
        """Start the work. Must be idempotent on run_id where the engine allows it."""

    @abstractmethod
    def get(self, workflow_ref: str, engine_run_id: str) -> EngineRun:
        ...

    def tasks(self, workflow_ref: str, engine_run_id: str) -> list[EngineTask]:
        raise EngineError(self.name, "task-level detail is not supported by this engine")

    @abstractmethod
    def available(self) -> tuple[bool, str | None]:
        """(reachable, why not). The reason matters: see EngineError."""
