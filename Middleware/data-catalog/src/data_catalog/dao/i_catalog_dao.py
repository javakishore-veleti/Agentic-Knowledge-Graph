"""DAO interfaces. Callers depend on these; implementations are resolved by DAO_FACTORY."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from ..dtos.catalog_dtos import (
    AppEndpointDto, DataInstanceDto, DataInstanceExecDto, DatasetDto, DomainDto,
    ListAppEndpointsReq, ListDataInstanceExecsReq, ListDataInstancesReq, ListDatasetsReq,
    ListDomainsReq, ListMiosReq, MioDto, MioLineageEdgeDto,
)


class IDomainDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListDomainsReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListDomainsReq, limit: int, after: str | None
    ) -> list[DomainDto]: ...


class IDatasetDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListDatasetsReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListDatasetsReq, limit: int, after: str | None
    ) -> list[DatasetDto]: ...


class IMioDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListMiosReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListMiosReq, limit: int, after: str | None
    ) -> list[MioDto]: ...

    @abstractmethod
    def exists(self, tenant_id: str, mio_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def lineage_parents(self, mio_id: uuid.UUID) -> list[MioLineageEdgeDto]: ...

    @abstractmethod
    def lineage_children(self, mio_id: uuid.UUID) -> list[MioLineageEdgeDto]: ...


class IDataInstanceDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListDataInstancesReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListDataInstancesReq, limit: int
    ) -> list[DataInstanceDto]: ...

    @abstractmethod
    def cdc_instance_id(self, tenant_id: str, mio_id: uuid.UUID) -> uuid.UUID | None: ...


class IDataInstanceExecDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListDataInstanceExecsReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListDataInstanceExecsReq, limit: int
    ) -> list[DataInstanceExecDto]: ...


class IAppEndpointDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListAppEndpointsReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListAppEndpointsReq, limit: int
    ) -> list[AppEndpointDto]: ...


class IHealthDao(ABC):
    @abstractmethod
    def probe(self) -> dict[str, Any]: ...
