"""Service interfaces. Every method takes a Ctx and returns a Resp (ADR-010)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..dtos.catalog_dtos import (
    GetMioLineageCtx, GetMioLineageResp, ListAppEndpointsCtx, ListAppEndpointsResp,
    ListDataInstanceExecsCtx, ListDataInstanceExecsResp, ListDataInstancesCtx,
    ListDataInstancesResp, ListDatasetsCtx, ListDatasetsResp, ListDomainsCtx,
    ListDomainsResp, ListMiosCtx, ListMiosResp,
)


class IDomainService(ABC):
    @abstractmethod
    def list_domains(self, ctx: ListDomainsCtx) -> ListDomainsResp: ...


class IDatasetService(ABC):
    @abstractmethod
    def list_datasets(self, ctx: ListDatasetsCtx) -> ListDatasetsResp: ...


class IMioService(ABC):
    @abstractmethod
    def list_mios(self, ctx: ListMiosCtx) -> ListMiosResp: ...

    @abstractmethod
    def list_data_instances(self, ctx: ListDataInstancesCtx) -> ListDataInstancesResp: ...

    @abstractmethod
    def get_lineage(self, ctx: GetMioLineageCtx) -> GetMioLineageResp: ...


class IDataInstanceExecService(ABC):
    @abstractmethod
    def list_execs(self, ctx: ListDataInstanceExecsCtx) -> ListDataInstanceExecsResp: ...


class IAppEndpointService(ABC):
    @abstractmethod
    def list_app_endpoints(self, ctx: ListAppEndpointsCtx) -> ListAppEndpointsResp: ...


class IHealthService(ABC):
    @abstractmethod
    def probe(self) -> dict: ...
