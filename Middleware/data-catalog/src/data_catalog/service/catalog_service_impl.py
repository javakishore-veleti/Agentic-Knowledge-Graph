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


from ..wf.catalog_wf import (  # noqa: E402
    AttachWorkflowWf, CreateMioWf, DeleteMioWf, DetachWorkflowWf, InvokeMioWorkflowWf,
    ListMioWorkflowsWf, ListWorkflowsWf, UpdateMioWf,
)
from .i_catalog_service import IMioWriteService, IWorkflowService  # noqa: E402


class WorkflowServiceImpl(IWorkflowService):
    def __init__(self) -> None:
        self._list_wf: IWorkflow = ListWorkflowsWf()
        self._mio_wfs: IWorkflow = ListMioWorkflowsWf()
        self._attach_wf: IWorkflow = AttachWorkflowWf()
        self._detach_wf: IWorkflow = DetachWorkflowWf()
        self._invoke_wf: IWorkflow = InvokeMioWorkflowWf()

    def list_workflows(self, ctx):
        return self._list_wf.run(ctx).require_resp()

    def list_mio_workflows(self, ctx):
        return self._mio_wfs.run(ctx).require_resp()

    def attach_workflow(self, ctx):
        return self._attach_wf.run(ctx).require_resp()

    def detach_workflow(self, ctx):
        return self._detach_wf.run(ctx).require_resp()

    def invoke(self, ctx):
        return self._invoke_wf.run(ctx).require_resp()


class MioWriteServiceImpl(IMioWriteService):
    def __init__(self) -> None:
        self._create_wf: IWorkflow = CreateMioWf()
        self._update_wf: IWorkflow = UpdateMioWf()
        self._delete_wf: IWorkflow = DeleteMioWf()

    def create_mio(self, ctx):
        return self._create_wf.run(ctx).require_resp()

    def update_mio(self, ctx):
        return self._update_wf.run(ctx).require_resp()

    def delete_mio(self, ctx):
        return self._delete_wf.run(ctx).require_resp()
