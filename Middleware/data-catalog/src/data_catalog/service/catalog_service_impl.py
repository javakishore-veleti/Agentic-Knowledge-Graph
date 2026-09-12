"""Service implementations.

Each method picks the workflow for its use case and runs it. The service holds no logic of
its own beyond that choice: the steps live in tasks, so a use case can be read as a list.

Singletons, stateless: the workflows are immutable wiring, and every piece of per-request
state is on the Ctx.
"""

from __future__ import annotations

from ..common.task import IWorkflow
from ..dao.i_catalog_dao import IHealthDao
from ..common.object_factory import DAO_FACTORY
from ..dtos.catalog_dtos import (
    GetMioLineageCtx, GetMioLineageResp, ListAppEndpointsCtx, ListAppEndpointsResp,
    ListDataInstanceExecsCtx, ListDataInstanceExecsResp, ListDataInstancesCtx,
    ListDataInstancesResp, ListDatasetsCtx, ListDatasetsResp, ListDomainsCtx,
    ListDomainsResp, ListMiosCtx, ListMiosResp,
)
from ..wf.catalog_wf import (
    GetMioLineageWf, ListAppEndpointsWf, ListDataInstanceExecsWf, ListDataInstancesWf,
    ListDatasetsWf, ListDomainsWf, ListMiosWf,
)
from .i_catalog_service import (
    IAppEndpointService, IDataInstanceExecService, IDatasetService, IDomainService,
    IHealthService, IMioService,
)


class DomainServiceImpl(IDomainService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListDomainsWf()

    def list_domains(self, ctx: ListDomainsCtx) -> ListDomainsResp:
        return self._list_wf.run(ctx).require_resp()


class DatasetServiceImpl(IDatasetService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListDatasetsWf()

    def list_datasets(self, ctx: ListDatasetsCtx) -> ListDatasetsResp:
        return self._list_wf.run(ctx).require_resp()


class MioServiceImpl(IMioService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListMiosWf()
        self._instances_wf: IWorkflow = ListDataInstancesWf()
        self._lineage_wf: IWorkflow = GetMioLineageWf()

    def list_mios(self, ctx: ListMiosCtx) -> ListMiosResp:
        return self._list_wf.run(ctx).require_resp()

    def list_data_instances(self, ctx: ListDataInstancesCtx) -> ListDataInstancesResp:
        return self._instances_wf.run(ctx).require_resp()

    def get_lineage(self, ctx: GetMioLineageCtx) -> GetMioLineageResp:
        return self._lineage_wf.run(ctx).require_resp()


class DataInstanceExecServiceImpl(IDataInstanceExecService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListDataInstanceExecsWf()

    def list_execs(self, ctx: ListDataInstanceExecsCtx) -> ListDataInstanceExecsResp:
        return self._list_wf.run(ctx).require_resp()


class AppEndpointServiceImpl(IAppEndpointService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListAppEndpointsWf()

    def list_app_endpoints(self, ctx: ListAppEndpointsCtx) -> ListAppEndpointsResp:
        return self._list_wf.run(ctx).require_resp()


class HealthServiceImpl(IHealthService):
    """No workflow: one probe, no steps worth naming."""

    def probe(self) -> dict:
        dao: IHealthDao = DAO_FACTORY.get(IHealthDao)
        return dao.probe()
