"""The one module that names both an interface and its implementation (ADR-010).

Swapping an implementation -- a different cache tier, an in-memory DAO for tests -- is a
change here and nowhere else.
"""

from __future__ import annotations

from .cache.app_cache_service_impl import AppCacheServiceImpl
from .cache.i_app_cache_service import IAppCacheService
from .cache.memory_lru_cache_store import MemoryLruCacheStore
from .cache.redis_cache_store import RedisCacheStore
from .common.object_factory import DAO_FACTORY, SERVICE_FACTORY
from .config import settings
from .dao.catalog_dao_impl import (
    AppEndpointDaoImpl, DataInstanceDaoImpl, DataInstanceExecDaoImpl, DatasetDaoImpl,
    DomainDaoImpl, HealthDaoImpl, MioDaoImpl,
)
from .dao.app_endpoint_admin_dao_impl import AppEndpointAdminDaoImpl
from .dao.i_app_endpoint_admin_dao import IAppEndpointAdminDao
from .dao.dataset_endpoint_dao_impl import AcquisitionDaoImpl, DatasetEndpointDaoImpl
from .dao.i_dataset_endpoint_dao import IAcquisitionDao, IDatasetEndpointDao
from .dao.i_workflow_dao import IInvocationDao, IMioWriteDao, IWorkflowDao
from .dao.workflow_dao_impl import InvocationDaoImpl, MioWriteDaoImpl, WorkflowDaoImpl
from .dao.i_catalog_dao import (
    IAppEndpointDao, IDataInstanceDao, IDataInstanceExecDao, IDatasetDao, IDomainDao,
    IHealthDao, IMioDao,
)
from .db import SessionLocal
from .integration.i_orchestrator_client import IOrchestratorClient
from .integration.orchestrator_client_impl import OrchestratorClientImpl
from .service.catalog_service_impl import (
    MioWriteServiceImpl, WorkflowServiceImpl,
    AppEndpointServiceImpl, DataInstanceExecServiceImpl, DatasetServiceImpl,
    DomainServiceImpl, HealthServiceImpl, MioServiceImpl,
)
from .service.app_endpoint_admin_service_impl import AppEndpointAdminServiceImpl
from .service.i_app_endpoint_admin_service import IAppEndpointAdminService
from .service.dataset_location_service_impl import DatasetLocationServiceImpl
from .service.i_dataset_location_service import IDatasetLocationService
from .service.i_catalog_service import (
    IMioWriteService, IWorkflowService, IAppEndpointService, IDataInstanceExecService, IDatasetService, IDomainService,
    IHealthService, IMioService,
)


def register_all() -> None:
    """Idempotent: safe to call from app startup and from a test fixture."""

    # --- service -> dao ------------------------------------------------------
    DAO_FACTORY.register(IDomainDao, lambda: DomainDaoImpl(SessionLocal))
    DAO_FACTORY.register(IDatasetDao, lambda: DatasetDaoImpl(SessionLocal))
    DAO_FACTORY.register(IMioDao, lambda: MioDaoImpl(SessionLocal))
    DAO_FACTORY.register(IDataInstanceDao, lambda: DataInstanceDaoImpl(SessionLocal))
    DAO_FACTORY.register(IDataInstanceExecDao, lambda: DataInstanceExecDaoImpl(SessionLocal))
    DAO_FACTORY.register(IAppEndpointDao, lambda: AppEndpointDaoImpl(SessionLocal))
    DAO_FACTORY.register(IHealthDao, lambda: HealthDaoImpl(SessionLocal))
    DAO_FACTORY.register(IWorkflowDao, lambda: WorkflowDaoImpl(SessionLocal))
    DAO_FACTORY.register(IMioWriteDao, lambda: MioWriteDaoImpl(SessionLocal))
    DAO_FACTORY.register(IInvocationDao, lambda: InvocationDaoImpl(SessionLocal))
    DAO_FACTORY.register(IDatasetEndpointDao, lambda: DatasetEndpointDaoImpl(SessionLocal))
    DAO_FACTORY.register(IAcquisitionDao, lambda: AcquisitionDaoImpl(SessionLocal))
    DAO_FACTORY.register(IAppEndpointAdminDao, lambda: AppEndpointAdminDaoImpl(SessionLocal))

    # --- api -> service ------------------------------------------------------
    SERVICE_FACTORY.register(IDomainService, DomainServiceImpl)
    SERVICE_FACTORY.register(IDatasetService, DatasetServiceImpl)
    SERVICE_FACTORY.register(IMioService, MioServiceImpl)
    SERVICE_FACTORY.register(IDataInstanceExecService, DataInstanceExecServiceImpl)
    SERVICE_FACTORY.register(IAppEndpointService, AppEndpointServiceImpl)
    SERVICE_FACTORY.register(IHealthService, HealthServiceImpl)
    SERVICE_FACTORY.register(IWorkflowService, WorkflowServiceImpl)
    SERVICE_FACTORY.register(IMioWriteService, MioWriteServiceImpl)
    SERVICE_FACTORY.register(IDatasetLocationService, DatasetLocationServiceImpl)
    SERVICE_FACTORY.register(IAppEndpointAdminService, AppEndpointAdminServiceImpl)

    # --- cache ---------------------------------------------------------------
    # The in-memory mirror is built only when the toggle is on, so a disabled mirror
    # cannot hold entries that a later toggle flip would serve as fresh.
    local = MemoryLruCacheStore(capacity=settings.cache_memory_capacity) \
        if settings.cache_mirror_in_memory else None
    SERVICE_FACTORY.register(
        IAppCacheService,
        lambda: AppCacheServiceImpl(
            RedisCacheStore(settings.redis_url),
            local,
            mirror_in_memory=settings.cache_mirror_in_memory,
            default_ttl_seconds=settings.cache_default_ttl_seconds,
        ),
    )

    # --- integration ---------------------------------------------------------
    SERVICE_FACTORY.register(
        IOrchestratorClient, lambda: OrchestratorClientImpl(settings.orchestrator_url)
    )
