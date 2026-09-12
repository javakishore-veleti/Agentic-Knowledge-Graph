"""DAO interface for dataset locations (ADR-012)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from ..dtos.catalog_dtos import (
    AddDatasetEndpointReq, DatasetEndpointDto, DatasetOverviewDto, ListDatasetsReq,
)


class IDatasetEndpointDao(ABC):
    @abstractmethod
    def for_dataset(
        self, tenant_id: str, dataset_id: uuid.UUID, role: str | None
    ) -> list[DatasetEndpointDto]: ...

    @abstractmethod
    def add(self, tenant_id: str, req: AddDatasetEndpointReq) -> uuid.UUID: ...

    @abstractmethod
    def overview(
        self, tenant_id: str, req: ListDatasetsReq, limit: int, after: str | None
    ) -> list[DatasetOverviewDto]: ...

    @abstractmethod
    def overview_count(self, tenant_id: str, req: ListDatasetsReq) -> int: ...


class IAcquisitionDao(ABC):
    """Claim and release acquisition of a dataset endpoint (ADR-013)."""

    @abstractmethod
    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict | None: ...

    @abstractmethod
    def claim(
        self, tenant_id: str, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool
    ) -> tuple[bool, str]:
        """Decision and transition in one statement, so two callers cannot both win."""

    @abstractmethod
    def complete(
        self, tenant_id: str, endpoint_id: uuid.UUID, status: str,
        bytes_written: int | None, object_count: int | None,
        error: dict | None, wf_ref_id: str | None,
    ) -> dict | None: ...

    @abstractmethod
    def stuck(self, tenant_id: str) -> list[dict]: ...
