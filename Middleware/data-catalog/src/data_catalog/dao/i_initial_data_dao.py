"""First-run data loading (ADR-017)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


class IInitialDataDao(ABC):
    @abstractmethod
    def status(self, tenant_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def claim(
        self, tracker_id: uuid.UUID, entity: str, tenant_id: str, env: str,
        trace_id: str, requested_by: str | None, force: bool,
    ) -> tuple[bool, str]:
        """Decision and transition in one statement, so two administrators pressing the
        same button cannot both be told to proceed."""

    @abstractmethod
    def apply_seed(self, entity: str, tenant_id: str) -> tuple[int, int]:
        """Insert the reference rows. Returns (inserted, skipped)."""

    @abstractmethod
    def complete(
        self, tracker_id: uuid.UUID, status: str, inserted: int, skipped: int,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> bool: ...
