"""Clients for the services this one depends on (ADR-010).

data-mgmt owns no database. The catalog owns dataset state; Airflow owns execution. This
service decides whether an acquisition should start and gets it started.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


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


class IAirflowClient(ABC):
    @abstractmethod
    def trigger(
        self, dag_id: str, dag_run_id: str, conf: dict[str, Any], trace_id: str
    ) -> str | None:
        """Start a DAG run and return immediately with its id.

        Asynchronous by contract: this never waits for the DAG. The run reports its own
        outcome by calling the catalog back.
        """

    @abstractmethod
    def run_state(self, dag_id: str, dag_run_id: str) -> str | None: ...

    @abstractmethod
    def available(self) -> bool: ...
