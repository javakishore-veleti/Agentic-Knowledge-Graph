from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


class IInitialDataService(ABC):
    @abstractmethod
    def status(self, tenant_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def load(
        self, entity: str, tenant_id: str, env: str, trace_id: str,
        requested_by: str | None, force: bool,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def report(
        self, tracker_id: uuid.UUID, status: str, inserted: int, skipped: int,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> dict[str, Any]: ...
