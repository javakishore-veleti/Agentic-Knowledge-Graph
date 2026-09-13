"""The one module naming both an interface and its implementation (ADR-010)."""

from __future__ import annotations

from akg_service_core import SERVICE_FACTORY

from .config import settings
from .integration.orchestrator_client_impl import OrchestratorClientImpl
from .integration.catalog_client_impl import CatalogClientImpl
from .integration.i_clients import ICatalogClient, IOrchestratorClient
from .service.acquisition_service_impl import AcquisitionServiceImpl
from .service.i_acquisition_service import IAcquisitionService


def register_all() -> None:
    SERVICE_FACTORY.register(IAcquisitionService, AcquisitionServiceImpl)
    SERVICE_FACTORY.register(
        ICatalogClient, lambda: CatalogClientImpl(settings.catalog_url)
    )
    SERVICE_FACTORY.register(
        IOrchestratorClient,
        lambda: OrchestratorClientImpl(
            settings.orchestrator_url, settings.orchestrator_timeout_seconds,
        ),
    )
