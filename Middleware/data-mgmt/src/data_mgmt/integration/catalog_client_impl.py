from __future__ import annotations

import uuid
from typing import Any

import httpx

from ..config import settings
from .i_clients import ICatalogClient


class CatalogClientImpl(ICatalogClient):
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base, timeout=self._timeout)

    def claim(
        self, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool, trace_id: str
    ) -> tuple[bool, str]:
        try:
            with self._client() as c:
                r = c.post(
                    f"/api/v1/dataset-endpoints/{endpoint_id}/claim",
                    json={"exec_id": str(exec_id), "force": force},
                    headers={"x-trace-id": trace_id},
                )
                if r.status_code >= 400:
                    return False, f"catalog_rejected_{r.status_code}"
                body = r.json()
                return bool(body.get("claimed")), str(body.get("reason", "unknown"))
        except Exception as exc:
            # Never assume a claim succeeded. Failing closed means nothing starts; failing
            # open would start a DAG the catalog knows nothing about.
            return False, f"catalog_unreachable: {type(exc).__name__}"

    def release(
        self, endpoint_id: uuid.UUID, status: str, error: dict[str, Any] | None, trace_id: str
    ) -> bool:
        try:
            with self._client() as c:
                r = c.post(
                    f"/api/v1/dataset-endpoints/{endpoint_id}/sync-status",
                    json={"status": status, "error": error},
                    headers={"x-trace-id": trace_id},
                )
                return r.status_code < 400
        except Exception:
            return False

    def endpoint(self, endpoint_id: uuid.UUID, trace_id: str) -> dict[str, Any] | None:
        try:
            with self._client() as c:
                r = c.get(f"/api/v1/dataset-endpoints/{endpoint_id}",
                          headers={"x-trace-id": trace_id})
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def available(self) -> bool:
        try:
            with self._client() as c:
                return c.get("/health", timeout=2.0).status_code == 200
        except Exception:
            return False
