"""Cross-cutting building blocks shared by every layer (ADR-010)."""

from .context import BaseCtx, TaskRecord
from .errors import NotFoundError, ServiceError, ValidationError
from .object_factory import DAO_FACTORY, SERVICE_FACTORY, ObjectFactory
from .paging import DEFAULT_LIMIT, MAX_LIMIT, clamp_limit, decode_cursor, encode_cursor
from .task import ITask, IWorkflow

__all__ = [
    "DAO_FACTORY", "DEFAULT_LIMIT", "MAX_LIMIT", "SERVICE_FACTORY", "BaseCtx",
    "ITask", "NotFoundError", "ObjectFactory", "ServiceError", "TaskRecord",
    "IWorkflow", "ValidationError", "clamp_limit", "decode_cursor", "encode_cursor",
]
