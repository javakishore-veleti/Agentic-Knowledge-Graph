"""The one module naming both an interface and its implementation (ADR-010)."""

from __future__ import annotations

from akg_service_core import SERVICE_FACTORY

from .config import settings
from .integration.airflow_client_impl import AirflowClientImpl
from .integration.catalog_client_impl import CatalogClientImpl
from .integration.i_clients import IAirflowClient, ICatalogClient
from .service.acquisition_service_impl import AcquisitionServiceImpl
from .service.i_acquisition_service import IAcquisitionService


def register_all() -> None:
    SERVICE_FACTORY.register(IAcquisitionService, AcquisitionServiceImpl)
    SERVICE_FACTORY.register(
        ICatalogClient, lambda: CatalogClientImpl(settings.catalog_url)
    )
    SERVICE_FACTORY.register(
        IAirflowClient,
        lambda: AirflowClientImpl(
            settings.airflow_url, settings.airflow_user, settings.airflow_password,
            settings.airflow_timeout_seconds,
        ),
    )
