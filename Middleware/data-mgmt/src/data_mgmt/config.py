"""Configuration. Same rule as every service: one env var selects the environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKG_", env_file=".env", extra="ignore")

    env: str = "local"
    tenant_id: str = "reference"
    api_prefix: str = "/api/v1"

    catalog_url: str = "http://localhost:8001"

    # Airflow's stable REST API.
    airflow_url: str = "http://localhost:8080"
    airflow_user: str = "admin"
    # Local only. In Azure this arrives from Key Vault via the container environment.
    airflow_password: str = ""
    airflow_timeout_seconds: float = 10.0

    #: Where Airflow should call back. Must be reachable FROM the Airflow container, which
    #: is not the same as reachable from this process -- inside Compose that is a service
    #: name, not localhost.
    catalog_callback_url: str = "http://akg-data-catalog:8001"

    acquisition_dag_id: str = "data_mgmt.acquisition.acquire_dataset_endpoint"
    export_dag_id: str = "data_mgmt.exports.export_dataset_endpoint"
    import_dag_id: str = "data_mgmt.imports.import_external_dataset"


settings = Settings()
