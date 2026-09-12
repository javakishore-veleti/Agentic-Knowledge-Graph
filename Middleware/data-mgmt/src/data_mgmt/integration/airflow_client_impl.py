"""Airflow's stable REST API. Trigger and return; never wait for the DAG."""

from __future__ import annotations

from typing import Any

import httpx

from .i_clients import IAirflowClient


class AirflowClientImpl(IAirflowClient):
    def __init__(self, base_url: str, user: str, password: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (user, password)
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base, auth=self._auth, timeout=self._timeout)

    def trigger(
        self, dag_id: str, dag_run_id: str, conf: dict[str, Any], trace_id: str
    ) -> str | None:
        try:
            with self._client() as c:
                r = c.post(
                    f"/api/v1/dags/{dag_id}/dagRuns",
                    json={"dag_run_id": dag_run_id, "conf": conf},
                    headers={"x-trace-id": trace_id},
                )
                if r.status_code == 409:
                    # Airflow already has a run with this id. The caller's id is derived
                    # from the exec id, so this means a retry of the same submission --
                    # the run exists, which is the outcome we wanted.
                    return dag_run_id
                if r.status_code >= 400:
                    return None
                return str(r.json().get("dag_run_id", dag_run_id))
        except Exception:
            return None

    def run_state(self, dag_id: str, dag_run_id: str) -> str | None:
        try:
            with self._client() as c:
                r = c.get(f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}")
                return str(r.json().get("state")) if r.status_code == 200 else None
        except Exception:
            return None

    def available(self) -> bool:
        try:
            with self._client() as c:
                return c.get("/health", timeout=3.0).status_code == 200
        except Exception:
            return False
