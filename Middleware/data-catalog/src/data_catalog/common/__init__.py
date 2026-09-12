"""Re-export of akg_service_core (ADR-010).

The primitives moved to Libraries/python/akg-service-core so a second service could use
them without copying. This module stays so existing imports keep working and the layering
test keeps seeing a `common` package.
"""

from akg_service_core import (
    DAO_FACTORY, DEFAULT_LIMIT, MAX_LIMIT, SERVICE_FACTORY, BaseCtx, ITask, IWorkflow,
    NotFoundError, ObjectFactory, ServiceError, TaskRecord, ValidationError, clamp_limit,
    decode_cursor, encode_cursor,
)
from akg_service_core import context, errors, object_factory, paging, task  # noqa: F401

__all__ = [
    "DAO_FACTORY", "DEFAULT_LIMIT", "MAX_LIMIT", "SERVICE_FACTORY", "BaseCtx", "ITask",
    "IWorkflow", "NotFoundError", "ObjectFactory", "ServiceError", "TaskRecord",
    "ValidationError", "clamp_limit", "decode_cursor", "encode_cursor",
]
