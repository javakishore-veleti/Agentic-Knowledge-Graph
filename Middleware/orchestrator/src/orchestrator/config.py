"""Configuration. One env var selects the environment; adapters read their own keys."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKG_", env_file=".env", extra="ignore")

    env: str = "local"
    tenant_id: str = "reference"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://akg:akg-local-only@localhost:5432/akg"

    #: Callers are services, not browsers -- but the Admin portal reads run history
    #: directly, so the portal origins are allowed. Never "*": this API starts workflows.
    cors_origins: str = "http://localhost:9003,http://localhost:9004"

    # --- Airflow adapter -----------------------------------------------------------
    airflow_url: str = "http://localhost:8080"
    airflow_user: str = "admin"
    #: Local only. In Azure this arrives from Key Vault via the container environment.
    airflow_password: str = ""
    airflow_timeout_seconds: float = 10.0


settings = Settings()
