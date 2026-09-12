"""Talking to the DataCatalog from inside a DAG.

Uses urllib rather than a client library so a DAG needs no dependency beyond the Airflow
image. The catalog base URL always arrives in dag_run.conf: inside Compose it is a service
name, and a DAG hard-coding localhost would be calling its own container.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from airflow.exceptions import AirflowFailException

log = logging.getLogger(__name__)


class CatalogCallback:
    def __init__(self, base_url: str, trace_id: str = "", timeout: int = 15) -> None:
        self.base = base_url.rstrip("/")
        self.trace_id = trace_id
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"content-type": "application/json", "x-trace-id": self.trace_id}

    def get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.base}{path}", headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read() or b"{}")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base}{path}", data=json.dumps(payload).encode(),
            headers=self._headers(), method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.URLError as exc:
            # Never swallow this. A report that silently fails strands the endpoint in
            # RUNNING and nothing can claim it again; failing lets Airflow retry.
            raise AirflowFailException(f"catalog unreachable at {self.base}: {exc}") from exc

    # ---- dataset endpoint acquisition -------------------------------------

    def dataset_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        ep = self.get(f"/api/v1/dataset-endpoints/{endpoint_id}")
        if not ep:
            raise AirflowFailException(f"dataset endpoint {endpoint_id} not found")
        return ep

    def report_sync(
        self,
        endpoint_id: str,
        status: str,
        *,
        bytes_written: int | None = None,
        object_count: int | None = None,
        error: dict[str, Any] | None = None,
        wf_ref_id: str | None = None,
    ) -> dict[str, Any]:
        """Report a terminal outcome.

        Data availability is decided by the catalog, not asserted here: a COMPLETED run
        that moved zero bytes leaves the endpoint unavailable, because the run finishing
        and the data arriving are different facts.
        """
        payload: dict[str, Any] = {"status": status, "wf_ref_id": wf_ref_id}
        if bytes_written is not None:
            payload["bytes"] = bytes_written
        if object_count is not None:
            payload["object_count"] = object_count
        if error is not None:
            payload["error"] = error
        out = self.post(f"/api/v1/dataset-endpoints/{endpoint_id}/sync-status", payload)
        log.info("catalog now reports state=%s wf=%s",
                 out.get("state"), out.get("sync_wf_status"))
        return out
