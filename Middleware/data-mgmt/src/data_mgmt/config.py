"""Configuration. Same rule as every service: one env var selects the environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKG_", env_file=".env", extra="ignore")

    env: str = "local"
    tenant_id: str = "reference"
    api_prefix: str = "/api/v1"

    #: Origins allowed to call this API from a browser. The portal calls this service
    #: directly -- acquisition does not route through the catalog -- so without this the
    #: Acquire button fails its preflight and the browser reports it as unreachable,
    #: which is indistinguishable from the service being down.
    #: Never "*": this API triggers workflows.
    cors_origins: str = "http://localhost:9003,http://localhost:9004"

    catalog_url: str = "http://localhost:9001"

    # Airflow's stable REST API.
    airflow_url: str = "http://localhost:8080"
    airflow_user: str = "admin"
    # Local only. In Azure this arrives from Key Vault via the container environment.
    airflow_password: str = ""
    airflow_timeout_seconds: float = 10.0

    #: Where Airflow should call back. Must be reachable FROM the Airflow container, which
    #: is not the same as reachable from this process.
    #:
    #: The default is host.docker.internal because in local development Airflow runs in a
    #: container while data-catalog runs on the host: a Compose service name does not
    #: resolve across that boundary, and the DAG failed on its first callback with a name
    #: lookup error that said nothing about why. Deployments where both sides are
    #: containers override this with the service name via AKG_CATALOG_CALLBACK_URL.
    catalog_callback_url: str = "http://host.docker.internal:9001"

    acquisition_dag_id: str = "data_mgmt.acquisition.acquire_dataset_endpoint"
    export_dag_id: str = "data_mgmt.exports.export_dataset_endpoint"
    import_dag_id: str = "data_mgmt.imports.import_external_dataset"


settings = Settings()
