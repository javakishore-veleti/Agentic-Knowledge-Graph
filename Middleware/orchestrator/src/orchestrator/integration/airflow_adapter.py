"""Airflow, behind the orchestration port.

Everything Airflow-shaped lives here: basic auth on /api/v1, dag_id as the workflow_ref,
dag_run_id as the engine run id, and its state vocabulary. No other module in the
platform should contain the word "dag".
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .i_engine import EngineError, EngineRun, EngineTask, IEngineAdapter

log = logging.getLogger(__name__)

#: Airflow's run states, mapped onto the one vocabulary callers see.
_RUN_STATES = {
    "queued": "queued",
    "running": "running",
    "success": "succeeded",
    "failed": "failed",
    # An Airflow run that is cleared or externally killed reports this.
    "upstream_failed": "failed",
}

#: Task instance states. More of them, and several mean "not finished".
_TASK_STATES = {
    "success": "succeeded",
    "failed": "failed",
    "upstream_failed": "failed",
    "running": "running",
    "queued": "queued",
    "scheduled": "queued",
    "deferred": "queued",
    "up_for_retry": "running",
    "up_for_reschedule": "running",
    "restarting": "running",
    "skipped": "succeeded",
    "removed": "cancelled",
    "none": "queued",
}


class AirflowAdapter(IEngineAdapter):
    name = "airflow"
    supports_tasks = True
    supports_cancel = False

    def __init__(self, base_url: str, user: str, password: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (user, password)
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base, auth=self._auth, timeout=self._timeout)

    def start(self, workflow_ref: str, run_id: str, conf: dict[str, Any],
              trace_id: str) -> EngineRun:
        try:
            with self._client() as c:
                r = c.post(
                    f"/api/v1/dags/{workflow_ref}/dagRuns",
                    json={"dag_run_id": run_id, "conf": conf},
                    headers={"x-trace-id": trace_id},
                )
        except httpx.HTTPError as exc:
            raise EngineError(self.name, f"could not reach Airflow: {exc}") from exc

        if r.status_code == 409:
            # Airflow already holds a run with this id. Our id is the orchestrator's own
            # run_id, so this is a retry of the same submission: the run exists, which is
            # the outcome we wanted. Read it back rather than reporting a conflict.
            return self.get(workflow_ref, run_id)

        if r.status_code == 403:
            raise EngineError(
                self.name,
                "Airflow returned 403. Its REST API needs the basic_auth backend enabled "
                "(AIRFLOW__API__AUTH_BACKENDS) and credentials that match the admin user; "
                "/health answers 200 without either, so a healthy Airflow can still refuse "
                "every API call.",
                403,
            )
        if r.status_code == 404:
            raise EngineError(
                self.name, f"Airflow has no DAG named {workflow_ref!r}", 404)
        if r.status_code >= 400:
            raise EngineError(
                self.name, f"Airflow refused the run: {r.status_code} {r.text[:200]}",
                r.status_code)

        body = r.json()
        return EngineRun(
            engine_run_id=str(body.get("dag_run_id", run_id)),
            state=_RUN_STATES.get(str(body.get("state", "queued")), "queued"),
            engine_state=body.get("state"),
            started_at=body.get("start_date"),
        )

    def get(self, workflow_ref: str, engine_run_id: str) -> EngineRun:
        try:
            with self._client() as c:
                r = c.get(f"/api/v1/dags/{workflow_ref}/dagRuns/{engine_run_id}")
        except httpx.HTTPError as exc:
            raise EngineError(self.name, f"could not reach Airflow: {exc}") from exc

        if r.status_code == 404:
            raise EngineError(self.name, "no such run", 404)
        if r.status_code >= 400:
            raise EngineError(
                self.name, f"{r.status_code} {r.text[:200]}", r.status_code)

        body = r.json()
        engine_state = str(body.get("state", ""))
        return EngineRun(
            engine_run_id=engine_run_id,
            state=_RUN_STATES.get(engine_state, "running"),
            engine_state=engine_state,
            started_at=body.get("start_date"),
            finished_at=body.get("end_date"),
        )

    def tasks(self, workflow_ref: str, engine_run_id: str) -> list[EngineTask]:
        try:
            with self._client() as c:
                r = c.get(
                    f"/api/v1/dags/{workflow_ref}/dagRuns/{engine_run_id}/taskInstances")
        except httpx.HTTPError as exc:
            raise EngineError(self.name, f"could not reach Airflow: {exc}") from exc
        if r.status_code >= 400:
            raise EngineError(
                self.name, f"{r.status_code} {r.text[:200]}", r.status_code)

        out: list[EngineTask] = []
        for ti in r.json().get("task_instances", []):
            engine_state = str(ti.get("state") or "none")
            out.append(EngineTask(
                task_id=str(ti.get("task_id")),
                state=_TASK_STATES.get(engine_state, "running"),
                engine_state=engine_state,
                started_at=ti.get("start_date"),
                finished_at=ti.get("end_date"),
                try_number=ti.get("try_number"),
            ))
        return out

    def available(self) -> tuple[bool, str | None]:
        """Probes the API, not /health.

        /health needs no authentication at all, so it answers 200 while every real call
        returns 403. Reporting that as "available" is how a misconfigured auth backend
        stayed hidden behind a green health check.
        """
        try:
            with self._client() as c:
                r = c.get("/api/v1/dags", params={"limit": 1}, timeout=3.0)
        except httpx.HTTPError as exc:
            return False, str(exc)
        if r.status_code == 200:
            return True, None
        if r.status_code in (401, 403):
            return False, (
                f"{r.status_code}: the REST API rejected the credentials. Check "
                f"AIRFLOW__API__AUTH_BACKENDS includes basic_auth and the password matches."
            )
        return False, f"{r.status_code} from /api/v1/dags"
