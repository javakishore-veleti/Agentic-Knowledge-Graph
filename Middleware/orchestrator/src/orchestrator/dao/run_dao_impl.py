"""SQL for orch.wf_run. No business rules: those are the service's."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..dtos.run_dtos import TERMINAL_STATES
from .i_run_dao import IRunDao


def _jsonable(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in dict(row).items():
        if isinstance(v, uuid.UUID):
            out[k] = str(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class RunDaoImpl(IRunDao):
    def __init__(self) -> None:
        self._engine = create_engine(settings.database_url, pool_pre_ping=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(bind=self._engine)

    def insert_or_get(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._session_factory() as s:
            # ON CONFLICT over the partial unique index makes the idempotency check and
            # the insert a single statement. RETURNING fires only for a real insert, so an
            # empty result is exactly the "someone else already has this key" case.
            inserted = s.execute(
                text(
                    "INSERT INTO orch.wf_run "
                    "  (run_id, engine, workflow_ref, run_key, state, conf, caller_ref, "
                    "   trace_id, tenant_id) "
                    "VALUES (:run_id, :engine, :workflow_ref, :run_key, 'queued', "
                    "        CAST(:conf AS jsonb), CAST(:caller_ref AS jsonb), "
                    "        :trace_id, :tenant_id) "
                    "ON CONFLICT (tenant_id, engine, workflow_ref, run_key) "
                    "  WHERE run_key IS NOT NULL DO NOTHING "
                    "RETURNING *"
                ),
                {**row, "conf": json.dumps(row["conf"]),
                 "caller_ref": json.dumps(row["caller_ref"])},
            ).mappings().first()

            if inserted is not None:
                s.commit()
                return _jsonable(inserted), True

            existing = s.execute(
                text("SELECT * FROM orch.wf_run "
                     " WHERE tenant_id = :tenant_id AND engine = :engine "
                     "   AND workflow_ref = :workflow_ref AND run_key = :run_key"),
                {k: row[k] for k in ("tenant_id", "engine", "workflow_ref", "run_key")},
            ).mappings().first()
            return (_jsonable(existing), False) if existing else ({}, False)

    def get(self, tenant_id: str, run_id: uuid.UUID) -> dict[str, Any] | None:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT * FROM orch.wf_run "
                     " WHERE run_id = :id AND tenant_id = :t"),
                {"id": run_id, "t": tenant_id},
            ).mappings().first()
            return _jsonable(row) if row else None

    def update_engine_run(self, run_id: uuid.UUID, engine_run_id: str | None,
                          state: str, engine_state: str | None,
                          error: dict[str, Any] | None) -> dict[str, Any] | None:
        terminal = state in TERMINAL_STATES
        with self._session_factory() as s:
            row = s.execute(
                text(
                    "UPDATE orch.wf_run SET "
                    "  engine_run_id = COALESCE(:engine_run_id, engine_run_id), "
                    "  state = :state, "
                    "  engine_state = :engine_state, "
                    "  error = CAST(:error AS jsonb), "
                    # started_at is set once, on the first move out of queued: a later
                    # poll must not keep pushing the start time forward.
                    "  started_at = CASE WHEN started_at IS NOT NULL THEN started_at "
                    "                    WHEN :state <> 'queued' THEN now() END, "
                    # The CHECK requires finished_at exactly for terminal states, so it is
                    # cleared if a run somehow moves back to running.
                    "  finished_at = CASE WHEN :terminal THEN COALESCE(finished_at, now()) "
                    "                     ELSE NULL END "
                    " WHERE run_id = :id RETURNING *"
                ),
                {"id": run_id, "engine_run_id": engine_run_id, "state": state,
                 "engine_state": engine_state,
                 "error": json.dumps(error) if error is not None else None,
                 "terminal": terminal},
            ).mappings().first()
            s.commit()
            return _jsonable(row) if row else None

    def list(self, tenant_id: str, engine: str | None, workflow_ref: str | None,
             state: str | None, limit: int, cursor: str | None
             ) -> tuple[list[dict[str, Any]], str | None]:
        # Keyset pagination on (created_at, run_id). Offsets shift under inserts, and runs
        # are inserted constantly -- a page 2 read with OFFSET silently skips rows.
        after = None
        if cursor:
            try:
                after = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            except Exception:
                after = None

        clauses = ["tenant_id = :t"]
        params: dict[str, Any] = {"t": tenant_id, "limit": limit + 1}
        if engine:
            clauses.append("engine = :engine")
            params["engine"] = engine
        if workflow_ref:
            clauses.append("workflow_ref = :wf")
            params["wf"] = workflow_ref
        if state:
            clauses.append("state = :state")
            params["state"] = state
        if after:
            clauses.append("(created_at, run_id) < (CAST(:after_at AS timestamptz), "
                           "CAST(:after_id AS uuid))")
            params["after_at"] = after.get("at")
            params["after_id"] = after.get("id")

        with self._session_factory() as s:
            rows = s.execute(
                text(f"SELECT * FROM orch.wf_run WHERE {' AND '.join(clauses)} "
                     " ORDER BY created_at DESC, run_id DESC LIMIT :limit"),
                params,
            ).mappings().all()

        items = [_jsonable(r) for r in rows]
        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            last = items[-1]
            next_cursor = base64.urlsafe_b64encode(
                json.dumps({"at": last["created_at"], "id": last["run_id"]}).encode()
            ).decode()
        return items, next_cursor
