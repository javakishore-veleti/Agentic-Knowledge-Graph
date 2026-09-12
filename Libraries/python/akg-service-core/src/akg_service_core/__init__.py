"""Layering primitives shared by every AKG middleware service (ADR-010).

Extracted from data-catalog so a second service does not copy them. Each service still
owns its own dependencies and deploys independently; what they share is the shape, not a
runtime.
"""

from .context import BaseCtx, TaskRecord
from .errors import NotFoundError, ServiceError, ValidationError
from .object_factory import DAO_FACTORY, SERVICE_FACTORY, ObjectFactory
from .paging import DEFAULT_LIMIT, MAX_LIMIT, clamp_limit, decode_cursor, encode_cursor
from .task import ITask, IWorkflow
from .validators import (
    redact_uri, uri_carries_credentials, uri_has_scheme,
)

__all__ = [
    "DAO_FACTORY", "DEFAULT_LIMIT", "MAX_LIMIT", "SERVICE_FACTORY", "BaseCtx", "ITask",
    "IWorkflow", "NotFoundError", "ObjectFactory", "ServiceError", "TaskRecord",
    "ValidationError", "clamp_limit", "decode_cursor", "encode_cursor",
    "redact_uri", "uri_carries_credentials", "uri_has_scheme",
]
