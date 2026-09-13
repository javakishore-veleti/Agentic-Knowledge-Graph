"""Persistence port for workflow runs."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


class IRunDao(ABC):
    @abstractmethod
    def insert_or_get(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Insert the run, or return the existing one with the same idempotency key.

        Returns (row, inserted). The decision and the write are one statement: checking
        first and inserting second lets two concurrent callers both pass the check.
        """

    @abstractmethod
    def get(self, tenant_id: str, run_id: uuid.UUID) -> dict[str, Any] | None: ...

    @abstractmethod
    def update_engine_run(self, run_id: uuid.UUID, engine_run_id: str | None,
                          state: str, engine_state: str | None,
                          error: dict[str, Any] | None) -> dict[str, Any] | None: ...

    @abstractmethod
    def list(self, tenant_id: str, engine: str | None, workflow_ref: str | None,
             state: str | None, limit: int, cursor: str | None
             ) -> tuple[list[dict[str, Any]], str | None]: ...
