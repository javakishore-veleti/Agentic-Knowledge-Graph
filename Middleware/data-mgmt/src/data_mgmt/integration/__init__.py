"""Clients for other services (ADR-010)."""

from .i_clients import IAirflowClient, ICatalogClient

__all__ = ["IAirflowClient", "ICatalogClient"]
