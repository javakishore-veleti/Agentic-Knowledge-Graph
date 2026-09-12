"""Clients for other services (ADR-010).

The catalog does not trigger workflows itself: it asks the orchestrator, which owns the
engine choice (ADR-008). The interface lives here so the service layer depends on a
contract rather than on HTTP.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from ..dtos.base_dtos import ItemDto


class WfExecSummaryDto(ItemDto):
    exec_id: uuid.UUID
    workflow: str
    status: str
    wf_ref_id: str | None


class IOrchestratorClient(ABC):
    @abstractmethod
    def execs_for_data_instance_exec(
        self, trace_id: str, data_instance_exec_id: uuid.UUID
    ) -> list[WfExecSummaryDto]:
        """Authoritative workflow executions for one catalog execution.

        wf_execs_json on the row is a cache of exactly this (ADR-009); this call is how
        the cache is refilled and how drift is resolved.
        """

    @abstractmethod
    def available(self) -> bool: ...
