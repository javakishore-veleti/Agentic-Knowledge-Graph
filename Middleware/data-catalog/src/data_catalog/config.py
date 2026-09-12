"""Configuration. One env var selects the environment; the rest comes from config.

No environment branching in code (ADR-002): the same image reads local or azure settings
and gets a different endpoint, never a different code path.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKG_", env_file=".env", extra="ignore")

    env: str = "local"
    # Local default only. In Azure this arrives from Key Vault through the container's
    # environment, and is never written into the catalog (ADR-009).
    database_url: str = "postgresql+psycopg://akg:akg-local-only@localhost:5432/akg"
    tenant_id: str = "reference"
    api_prefix: str = "/api/v1"
    echo_sql: bool = False

    # --- cache (ADR-011) ---
    redis_url: str = "redis://localhost:6379/0"
    #: Feature toggle for the in-process mirror of the shared cache.
    cache_mirror_in_memory: bool = True
    cache_memory_capacity: int = 1024
    cache_default_ttl_seconds: int = 300

    # --- integration ---
    orchestrator_url: str = "http://localhost:9002"

    #: "inline" seeds in-process; "workflow" hands it to the orchestrator and waits for
    #: the DAG to report back. Local defaults to inline so a fresh checkout works before
    #: Airflow is running.
    initial_data_mode: str = "inline"

    #: Origins allowed to call this API from a browser. The Angular dev server runs on a
    #: different port, so without this every portal request fails as a CORS error with
    #: nothing useful in the response. Production serves the portal behind the gateway on
    #: one origin and needs none of this.
    cors_origins: str = "http://localhost:9003,http://localhost:9004"


settings = Settings()
