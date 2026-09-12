from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any


class IAppEndpointAdminDao(ABC):
    @abstractmethod
    def create(self, tenant_id: str, data: dict[str, Any]) -> uuid.UUID: ...

    @abstractmethod
    def update(self, tenant_id: str, endpoint_id: uuid.UUID, changes: dict[str, Any]) -> bool: ...

    @abstractmethod
    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None: ...

    @abstractmethod
    def unconfigured(self, tenant_id: str) -> list[dict[str, Any]]: ...
