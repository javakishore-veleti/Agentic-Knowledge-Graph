"""DAO interfaces for the workflow master, MIO writes and invocation."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from ..dtos.catalog_dtos import (
    CreateMioReq, ListWorkflowsReq, MioDto, MioWorkflowDto, UpdateMioReq, WorkflowDto,
)


class IWorkflowDao(ABC):
    @abstractmethod
    def count(self, tenant_id: str, req: ListWorkflowsReq) -> int: ...

    @abstractmethod
    def find(
        self, tenant_id: str, req: ListWorkflowsReq, limit: int, after: str | None
    ) -> list[WorkflowDto]: ...

    @abstractmethod
    def get(self, tenant_id: str, workflow_id: uuid.UUID) -> WorkflowDto | None: ...

    @abstractmethod
    def for_mio(self, mio_id: uuid.UUID) -> list[MioWorkflowDto]: ...

    @abstractmethod
    def attach(
        self, mio_id: uuid.UUID, workflow_id: uuid.UUID, workflow_code: str,
        purpose: str, overrides: dict[str, Any],
    ) -> bool: ...

    @abstractmethod
    def detach(self, mio_id: uuid.UUID, workflow_id: uuid.UUID) -> bool: ...


class IMioWriteDao(ABC):
    @abstractmethod
    def create(self, tenant_id: str, req: CreateMioReq) -> uuid.UUID: ...

    @abstractmethod
    def update(self, tenant_id: str, req: UpdateMioReq) -> bool: ...

    @abstractmethod
    def delete(self, tenant_id: str, mio_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def get_overview(self, tenant_id: str, mio_id: uuid.UUID) -> MioDto | None: ...

    @abstractmethod
    def domain_id_for_code(self, tenant_id: str, domain_code: str) -> uuid.UUID | None: ...


class IInvocationDao(ABC):
    @abstractmethod
    def record_exec(
        self, tenant_id: str, env: str, trace_id: str, mio_id: uuid.UUID,
        workflow_code: str, input_data: dict[str, Any], requested_by: str | None,
        idempotency_key: str | None,
    ) -> tuple[uuid.UUID, str]:
        """Write the execution row BEFORE the engine is called and return its id.

        Returning the status too, because an idempotent replay returns the existing row
        rather than creating a second one.
        """
