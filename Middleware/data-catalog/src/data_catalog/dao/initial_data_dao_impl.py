from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from ..seed.reference_data import seed_entity
from .catalog_dao_impl import _BaseDao
from .i_initial_data_dao import IInitialDataDao


class InitialDataDaoImpl(_BaseDao, IInitialDataDao):
    def status(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as s:
            rows = s.execute(
                text("SELECT * FROM catalog.initial_data_status ORDER BY load_order")
            ).mappings().all()
            return [
                {k: (str(v) if isinstance(v, uuid.UUID)
                     else v.isoformat() if hasattr(v, "isoformat") else v)
                 for k, v in dict(r).items()}
                for r in rows
            ]

    def claim(
        self, tracker_id: uuid.UUID, entity: str, tenant_id: str, env: str,
        trace_id: str, requested_by: str | None, force: bool,
    ) -> tuple[bool, str]:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT claimed, reason FROM catalog.claim_initial_data_load("
                     ":id, :entity, :tenant, :env, :trace, :by, :force)"),
                {"id": tracker_id, "entity": entity, "tenant": tenant_id, "env": env,
                 "trace": trace_id, "by": requested_by, "force": force},
            ).mappings().first()
            s.commit()
        return (bool(row["claimed"]), str(row["reason"])) if row else (False, "unknown")

    def apply_seed(self, entity: str, tenant_id: str) -> tuple[int, int]:
        """One transaction for the whole entity.

        A partial seed is worse than none: half the domains present means the next load is
        refused as already_loaded while the data is incomplete.
        """
        with self._session_factory() as s:
            inserted, skipped = seed_entity(s, entity, tenant_id)
            s.commit()
        return inserted, skipped

    def complete(
        self, tracker_id: uuid.UUID, status: str, inserted: int, skipped: int,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> bool:
        with self._session_factory() as s:
            ok = s.scalar(
                text("SELECT catalog.complete_initial_data_load("
                     ":id, :status, :ins, :skip, CAST(:err AS jsonb), :ref)"),
                {"id": tracker_id, "status": status, "ins": inserted, "skip": skipped,
                 "err": None if error is None else json.dumps(error), "ref": wf_ref_id},
            )
            s.commit()
            return bool(ok)
