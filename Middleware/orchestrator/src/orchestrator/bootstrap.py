"""The one module naming both an interface and its implementation (ADR-010)."""

from __future__ import annotations

from akg_service_core import DAO_FACTORY, SERVICE_FACTORY

from .config import settings
from .dao.i_run_dao import IRunDao
from .dao.run_dao_impl import RunDaoImpl
from .integration.airflow_adapter import AirflowAdapter
from .service.i_run_service import IRunService
from .service.run_service_impl import RunServiceImpl


def _adapters() -> dict:
    """Every engine this deployment can drive.

    Adding Step Functions is one entry here plus one adapter class. Nothing else in the
    platform learns a new name: callers pass `engine` and read the same run shape back.
    """
    return {
        "airflow": AirflowAdapter(
            settings.airflow_url, settings.airflow_user, settings.airflow_password,
            settings.airflow_timeout_seconds,
        ),
    }


def register_all() -> None:
    DAO_FACTORY.register(IRunDao, RunDaoImpl)
    SERVICE_FACTORY.register(IRunService, lambda: RunServiceImpl(_adapters()))
