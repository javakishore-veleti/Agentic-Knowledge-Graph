"""First-run loading (ADR-017).

Claims, then seeds. Local deployments seed in-process because a fresh checkout should work
before Airflow is running; a cloud deployment hands the work to the orchestrator. The mode
is configuration, and the response says which was used rather than leaving the caller to
guess why a load finished instantly.
"""

from __future__ import annotations

import uuid
from typing import Any

from akg_service_core import ValidationError

from ..common.object_factory import DAO_FACTORY
from ..config import settings
from ..dao.i_initial_data_dao import IInitialDataDao
from ..seed.reference_data import SEED_SETS
from .i_initial_data_service import IInitialDataService


class InitialDataServiceImpl(IInitialDataService):
    def status(self, tenant_id: str) -> list[dict[str, Any]]:
        return DAO_FACTORY.get(IInitialDataDao).status(tenant_id)

    def load(
        self, entity: str, tenant_id: str, env: str, trace_id: str,
        requested_by: str | None, force: bool,
    ) -> dict[str, Any]:
        if entity not in SEED_SETS:
            raise ValidationError(
                f"unknown entity {entity!r}; expected one of {sorted(SEED_SETS)}", trace_id
            )

        dao: IInitialDataDao = DAO_FACTORY.get(IInitialDataDao)
        tracker_id = uuid.uuid4()
        claimed, reason = dao.claim(
            tracker_id, entity, tenant_id, env, trace_id, requested_by, force
        )
        if not claimed:
            # Not an error: already_loaded is the expected answer to pressing the button
            # a second time, and the whole reason the tracker exists.
            return {"entity": entity, "claimed": False, "reason": reason}

        if settings.initial_data_mode == "workflow":
            # The orchestrator triggers the DAG, which reports back to /status. The
            # tracker stays PENDING until it does, which is what makes a failed submit
            # visible rather than silent.
            return {"entity": entity, "claimed": True, "reason": "claimed",
                    "tracker_id": str(tracker_id), "mode": "workflow"}

        try:
            inserted, skipped = dao.apply_seed(entity, tenant_id)
        except Exception as exc:
            dao.complete(tracker_id, "FAILED", 0, 0,
                         {"detail": f"{type(exc).__name__}"}, None)
            raise
        dao.complete(tracker_id, "SUCCEEDED", inserted, skipped, None, None)
        return {"entity": entity, "claimed": True, "reason": "claimed",
                "tracker_id": str(tracker_id), "mode": "inline",
                "inserted": inserted, "skipped": skipped}

    def report(
        self, tracker_id: uuid.UUID, status: str, inserted: int, skipped: int,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> dict[str, Any]:
        if status not in {"RUNNING", "SUCCEEDED", "FAILED"}:
            raise ValidationError(f"unexpected status {status!r}", None)
        ok = DAO_FACTORY.get(IInitialDataDao).complete(
            tracker_id, status, inserted, skipped, error, wf_ref_id
        )
        return {"tracker_id": str(tracker_id), "updated": ok}
