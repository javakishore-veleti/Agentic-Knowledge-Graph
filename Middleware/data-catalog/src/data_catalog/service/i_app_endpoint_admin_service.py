from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


class IAppEndpointAdminService(ABC):
    @abstractmethod
    def create(self, tenant_id: str, data: dict[str, Any], trace_id: str) -> uuid.UUID: ...

    @abstractmethod
    def update(
        self, tenant_id: str, endpoint_id: uuid.UUID, changes: dict[str, Any], trace_id: str
    ) -> bool: ...

    @abstractmethod
    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None: ...

    @abstractmethod
    def unconfigured(self, tenant_id: str) -> list[dict[str, Any]]: ...
