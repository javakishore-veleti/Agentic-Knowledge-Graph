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

    #: The orchestrator runs workflows on this service's behalf. Airflow's URL,
    #: credentials and API version live there, not here.
    orchestrator_url: str = "http://localhost:9005"
    orchestrator_timeout_seconds: float = 10.0

    #: Which engine runs acquisition, and what to run on it. Both are configuration:
    #: moving acquisition to Step Functions is an env var, not a code change here.
    acquisition_engine: str = "airflow"
    acquisition_workflow_ref: str = "data_mgmt.acquisition.acquire_dataset_endpoint"
    export_workflow_ref: str = "data_mgmt.exports.export_dataset_endpoint"
    import_workflow_ref: str = "data_mgmt.imports.import_external_dataset"


settings = Settings()
