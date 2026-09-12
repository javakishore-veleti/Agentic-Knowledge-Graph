"""HTTP routers. Thin by rule: bind, delegate, return (ADR-010)."""

from .catalog_api import router as catalog_router
from .dataset_endpoint_api import router as dataset_endpoint_router
from .workflow_api import router as workflow_router

__all__ = ["catalog_router", "dataset_endpoint_router", "workflow_router"]
