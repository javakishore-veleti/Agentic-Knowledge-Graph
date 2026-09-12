"""Workflows: one per use case, each an ordered set of tasks (ADR-010).

Reading a workflow's task list is the fastest way to understand what a use case does. The
tasks are constructed once at import and held in a tuple, because the sequence is wiring
rather than state -- nothing appends to it at runtime.
"""

from __future__ import annotations

from ..common.task import ITask, IWorkflow
from ..dtos.cache_dtos import CacheStrategyName
from ..tasks.catalog_tasks import (
    BuildAppEndpointsRespTask, BuildDataInstancesRespTask, BuildDatasetsRespTask,
    BuildDomainsRespTask, BuildExecsRespTask, BuildLineageRespTask, BuildMiosRespTask,
    CacheLookupTask, CacheStoreTask, CountDatasetsTask, CountDomainsTask, CountMiosTask,
    FetchAppEndpointsTask, FetchDataInstancesTask, FetchDatasetsTask, FetchDomainsTask,
    FetchExecsTask, FetchLineageTask, FetchMiosTask, ResolvePagingTask,
    VerifyMioExistsTask,
)

CACHE_DOMAINS = "catalog.domains"
CACHE_DATASETS = "catalog.datasets"
CACHE_MIOS = "catalog.mios"
CACHE_ENDPOINTS = "catalog.app_endpoints"


class ListDomainsWf(IWorkflow):
    name = "list_domains_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            CacheLookupTask(CACHE_DOMAINS),
            CountDomainsTask(),
            FetchDomainsTask(),
            BuildDomainsRespTask(),
            CacheStoreTask(CACHE_DOMAINS, strategy=CacheStrategyName.TTL),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListDatasetsWf(IWorkflow):
    name = "list_datasets_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            CacheLookupTask(CACHE_DATASETS),
            CountDatasetsTask(),
            FetchDatasetsTask(),
            BuildDatasetsRespTask(),
            # Category = domain: every dataset listing for a domain becomes wrong the
            # moment a dataset in it changes, and per-key TTLs cannot express that.
            CacheStoreTask(
                CACHE_DATASETS, strategy=CacheStrategyName.CATEGORY, category_from="domain"
            ),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListMiosWf(IWorkflow):
    name = "list_mios_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            CacheLookupTask(CACHE_MIOS),
            CountMiosTask(),
            FetchMiosTask(),
            BuildMiosRespTask(),
            CacheStoreTask(
                CACHE_MIOS, strategy=CacheStrategyName.CATEGORY, category_from="domain"
            ),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListDataInstancesWf(IWorkflow):
    """Not cached: instance state changes continuously, and a stale realtime or cdc
    instance state is worse than a slightly slower page."""

    name = "list_data_instances_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            VerifyMioExistsTask(),
            FetchDataInstancesTask(),
            BuildDataInstancesRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListDataInstanceExecsWf(IWorkflow):
    name = "list_data_instance_execs_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            FetchExecsTask(),
            BuildExecsRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListAppEndpointsWf(IWorkflow):
    name = "list_app_endpoints_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(),
            CacheLookupTask(CACHE_ENDPOINTS),
            FetchAppEndpointsTask(),
            BuildAppEndpointsRespTask(),
            # Endpoints change rarely; a longer LRU window suits them better than a TTL.
            CacheStoreTask(CACHE_ENDPOINTS, strategy=CacheStrategyName.LRU_COUNT),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class GetMioLineageWf(IWorkflow):
    name = "get_mio_lineage_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            VerifyMioExistsTask(),
            FetchLineageTask(),
            BuildLineageRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


# ================================================================ workflow master,
#                                                                  MIO writes, invoke

from ..tasks.workflow_tasks import (  # noqa: E402
    AttachWorkflowTask, BuildCreateMioRespTask, BuildInvokeRespTask,
    BuildWorkflowsRespTask, CountWorkflowsTask, CreateMioTask, DeleteMioTask,
    DetachWorkflowTask, FetchMioWorkflowsTask, FetchWorkflowsTask,
    InvalidateMioCachesTask, RecordInvocationTask, ResolveWorkflowForInvokeTask,
    SubmitToOrchestratorTask,
    UpdateMioTask, ValidateCreateMioTask, ValidateInvokeParamsTask,
    ValidateMioTransitionTask,
    VerifyMioForWriteTask,
)


class ListWorkflowsWf(IWorkflow):
    name = "list_workflows_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ResolvePagingTask(), CountWorkflowsTask(), FetchWorkflowsTask(),
            BuildWorkflowsRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class CreateMioWf(IWorkflow):
    name = "create_mio_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            ValidateCreateMioTask(), CreateMioTask(), BuildCreateMioRespTask(),
            InvalidateMioCachesTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class UpdateMioWf(IWorkflow):
    name = "update_mio_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            VerifyMioForWriteTask(), ValidateMioTransitionTask(), UpdateMioTask(),
            InvalidateMioCachesTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class DeleteMioWf(IWorkflow):
    name = "delete_mio_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            VerifyMioForWriteTask(), DeleteMioTask(), InvalidateMioCachesTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class ListMioWorkflowsWf(IWorkflow):
    name = "list_mio_workflows_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (VerifyMioForWriteTask(), FetchMioWorkflowsTask())

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class AttachWorkflowWf(IWorkflow):
    name = "attach_workflow_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (VerifyMioForWriteTask(), AttachWorkflowTask())

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class DetachWorkflowWf(IWorkflow):
    name = "detach_workflow_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (VerifyMioForWriteTask(), DetachWorkflowTask())

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class InvokeMioWorkflowWf(IWorkflow):
    """Validate, record, then submit -- in that order.

    Recording before submitting is what makes a failed submit visible; validating before
    recording is what keeps a rejected request from leaving a PENDING row that looks like
    a stuck one.
    """

    name = "invoke_mio_workflow_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            VerifyMioForWriteTask(),
            ResolveWorkflowForInvokeTask(),
            ValidateInvokeParamsTask(),
            RecordInvocationTask(),
            SubmitToOrchestratorTask(),
            BuildInvokeRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks
