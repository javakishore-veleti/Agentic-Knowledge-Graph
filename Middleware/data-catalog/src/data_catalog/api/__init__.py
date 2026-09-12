"""HTTP routers. Thin by rule: bind, delegate, return (ADR-010)."""

from .app_endpoint_api import router as app_endpoint_router
from .catalog_api import router as catalog_router
from .dataset_endpoint_api import router as dataset_endpoint_router
from .initial_data_api import router as initial_data_router
from .workflow_api import router as workflow_router

__all__ = [
    "app_endpoint_router", "catalog_router", "dataset_endpoint_router",
    "initial_data_router", "workflow_router",
]
