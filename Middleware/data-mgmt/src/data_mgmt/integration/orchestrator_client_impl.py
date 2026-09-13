"""The orchestrator, over HTTP.

This service no longer knows what a DAG is. It names a workflow and an engine; which
engine and how to authenticate to it are the orchestrator's problem. That boundary is the
reason the service exists: Airflow's auth backend and URL layout had leaked in here, and
every future caller would have inherited the same leak.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .i_clients import IOrchestratorClient, RunHandle

log = logging.getLogger(__name__)


class OrchestratorClientImpl(IOrchestratorClient):
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def start(self, engine: str, workflow_ref: str, run_key: str,
              conf: dict[str, Any], caller_ref: dict[str, Any],
              trace_id: str) -> RunHandle | None:
        try:
            with httpx.Client(base_url=self._base, timeout=self._timeout) as c:
                r = c.post(
                    "/api/v1/runs",
                    json={"engine": engine, "workflow_ref": workflow_ref,
                          "run_key": run_key, "conf": conf, "caller_ref": caller_ref},
                    headers={"x-trace-id": trace_id},
                )
        except httpx.HTTPError as exc:
            log.warning("orchestrator unreachable: %s", exc)
            return None

        if r.status_code >= 400:
            log.warning("orchestrator refused the run: %s %s", r.status_code, r.text[:200])
            return None

        body = r.json()
        run = body.get("run", {})
        # `started: false` with reason already_started is still a usable handle: the run
        # exists, which is what the caller needed. Only an engine refusal is a failure.
        if not body.get("started") and not str(body.get("reason", "")).startswith("already"):
            return RunHandle(run_id=run.get("run_id"), state=run.get("state", "failed"),
                             accepted=False, reason=str(body.get("reason", "refused")))
        return RunHandle(run_id=run.get("run_id"), state=run.get("state", "queued"),
                         accepted=True, reason=str(body.get("reason", "started")))

    def state(self, run_id: str, trace_id: str) -> str | None:
        try:
            with httpx.Client(base_url=self._base, timeout=self._timeout) as c:
                r = c.get(f"/api/v1/runs/{run_id}", headers={"x-trace-id": trace_id})
                if r.status_code != 200:
                    return None
                return str(r.json().get("run", {}).get("state"))
        except httpx.HTTPError:
            return None

    def available(self) -> bool:
        try:
            with httpx.Client(base_url=self._base, timeout=3.0) as c:
                return c.get("/health").status_code == 200
        except httpx.HTTPError:
            return False
