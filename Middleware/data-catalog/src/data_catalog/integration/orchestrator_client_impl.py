"""HTTP client for the orchestrator service.

Every call carries the caller's trace_id, so one id spans both services. A dependency
being down degrades the response rather than failing it: the catalog can still list, it
simply cannot refresh the workflow cache.
"""

from __future__ import annotations

import uuid
from typing import Any

from .i_orchestrator_client import IOrchestratorClient, WfExecSummaryDto


class OrchestratorClientImpl(IOrchestratorClient):
    def __init__(self, base_url: str, timeout_seconds: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def _client(self) -> Any:
        import httpx

        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    def execs_for_data_instance_exec(
        self, trace_id: str, data_instance_exec_id: uuid.UUID
    ) -> list[WfExecSummaryDto]:
        try:
            with self._client() as c:
                r = c.get(
                    f"/api/v1/wf-execs",
                    params={"data_instance_exec_id": str(data_instance_exec_id)},
                    headers={"x-trace-id": trace_id},
                )
                r.raise_for_status()
                return [WfExecSummaryDto.model_validate(i) for i in r.json().get("items", [])]
        except Exception:
            # An empty list is honest here: we do not know of any. The caller falls back
            # to the cached wf_execs_json rather than failing.
            return []

    def available(self) -> bool:
        try:
            with self._client() as c:
                return c.get("/health", timeout=1.0).status_code == 200
        except Exception:
            return False
