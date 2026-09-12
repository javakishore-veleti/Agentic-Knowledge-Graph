"""Configuration. One env var selects the environment; the rest comes from config.

No environment branching in code (ADR-002): the same image reads local.yaml or
azure-dev.yaml and gets a different endpoint, never a different code path.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKG_", env_file=".env", extra="ignore")

    env: str = "local"
    # Local default only. In Azure this arrives from Key Vault via the container's
    # environment, and the value is never written to the catalog (ADR-009).
    database_url: str = "postgresql+psycopg://akg:akg-local-only@localhost:5432/akg"
    tenant_id: str = "reference"
    api_prefix: str = "/api/v1"
    echo_sql: bool = False


settings = Settings()
