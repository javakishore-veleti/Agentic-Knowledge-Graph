"""Clients for the services this one depends on (ADR-010).

data-mgmt owns no database. The catalog owns dataset state; the orchestrator owns execution. This
service decides whether an acquisition should start and gets it started.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, NamedTuple


class ICatalogClient(ABC):
    @abstractmethod
    def claim(
        self, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool, trace_id: str
    ) -> tuple[bool, str]:
        """Ask the catalog to claim this endpoint for acquisition.

        The catalog decides, not this service: the decision and the state transition have
        to be one statement or two callers both start a DAG against one destination.
        Returns (claimed, reason).
        """

    @abstractmethod
    def release(
        self, endpoint_id: uuid.UUID, status: str, error: dict[str, Any] | None, trace_id: str
    ) -> bool:
        """Report a terminal outcome. Used when the submit fails after a claim: without
        it the endpoint would sit RUNNING until the stuck-sync sweeper noticed."""

    @abstractmethod
    def endpoint(self, endpoint_id: uuid.UUID, trace_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def available(self) -> bool: ...


class RunHandle(NamedTuple):
    run_id: str | None
    state: str
    #: False when no run is in flight. `reason` says why, and the caller must release
    #: whatever it claimed -- a claim held for a run that never started is the endpoint
    #: stuck RUNNING until a sweeper notices.
    accepted: bool
    reason: str


class IOrchestratorClient(ABC):
    """Workflow execution, engine-neutral.

    Deliberately says nothing about DAGs. An implementation may run the work on Airflow,
    Step Functions or anything else; this service is not entitled to know which.
    """

    @abstractmethod
    def start(self, engine: str, workflow_ref: str, run_key: str,
              conf: dict[str, Any], caller_ref: dict[str, Any],
              trace_id: str) -> "RunHandle | None":
        """Start a run and return immediately.

        Asynchronous by contract: never waits. The run reports its own outcome by calling
        the catalog back. `run_key` makes a retried submission return the same run rather
        than starting a second one.
        """

    @abstractmethod
    def state(self, run_id: str, trace_id: str) -> str | None: ...

    @abstractmethod
    def available(self) -> bool: ...
