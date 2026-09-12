"""HTTP routers (ADR-010)."""

from .acquisition_api import router as acquisition_router

__all__ = ["acquisition_router"]
