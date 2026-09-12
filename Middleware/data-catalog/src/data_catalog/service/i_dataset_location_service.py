"""Dataset locations and acquisition state (ADR-012, ADR-013)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from ..dtos.catalog_dtos import AddDatasetEndpointReq, DatasetEndpointDto


class IDatasetLocationService(ABC):
    @abstractmethod
    def list_locations(
        self, tenant_id: str, dataset_id: uuid.UUID, role: str | None, trace_id: str
    ) -> list[DatasetEndpointDto]: ...

    @abstractmethod
    def add_location(
        self, tenant_id: str, req: AddDatasetEndpointReq, trace_id: str
    ) -> uuid.UUID: ...

    @abstractmethod
    def get_location(
        self, tenant_id: str, endpoint_id: uuid.UUID
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    def claim(
        self, tenant_id: str, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool,
        trace_id: str,
    ) -> tuple[bool, str]: ...

    @abstractmethod
    def report_sync(
        self, tenant_id: str, endpoint_id: uuid.UUID, status: str,
        bytes_written: int | None, object_count: int | None,
        error: dict[str, Any] | None, wf_ref_id: str | None, trace_id: str,
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    def stuck(self, tenant_id: str) -> list[dict[str, Any]]: ...
