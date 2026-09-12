"""HTTP routers. Thin by rule: bind, delegate, return (ADR-010)."""

from .catalog_api import router as catalog_router

__all__ = ["catalog_router"]
