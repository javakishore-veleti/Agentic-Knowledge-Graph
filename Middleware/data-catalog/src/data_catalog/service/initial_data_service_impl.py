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

from ..cache.i_app_cache_service import IAppCacheService
from ..common.object_factory import DAO_FACTORY, SERVICE_FACTORY
from ..config import settings
from ..dao.i_initial_data_dao import IInitialDataDao
from ..seed.reference_data import SEED_SETS
from ..wf.catalog_wf import CACHE_DATASETS, CACHE_DOMAINS, CACHE_ENDPOINTS, CACHE_MIOS
from .i_initial_data_service import IInitialDataService

#: Which cached listings a seed invalidates. Seeding domains and then serving a cached
#: empty domain list is the same failure that made a newly created MIO invisible: the
#: write happened, the read did not know.
_CACHES_TOUCHED: dict[str, tuple[str, ...]] = {
    "domains": (CACHE_DOMAINS, CACHE_DATASETS, CACHE_MIOS),
    "datasets": (CACHE_DATASETS, CACHE_MIOS),
    "endpoints": (CACHE_ENDPOINTS,),
    "purposes": (),
    "workflows": (),
}


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
        self._invalidate(entity, tenant_id)
        return {"entity": entity, "claimed": True, "reason": "claimed",
                "tracker_id": str(tracker_id), "mode": "inline",
                "inserted": inserted, "skipped": skipped}

    @staticmethod
    def _invalidate(entity: str, tenant_id: str) -> None:
        """Drop the listings the seed just made wrong.

        Seeding domains invalidates datasets and MIOs too: their listings are filtered by
        domain, so a cached page computed when no domain existed stays empty.
        """
        caches = _CACHES_TOUCHED.get(entity, ())
        if not caches:
            return
        cache: IAppCacheService = SERVICE_FACTORY.get(IAppCacheService)
        for name in caches:
            cache.evict_all(name, tenant_id)

    def report(
        self, tracker_id: uuid.UUID, status: str, inserted: int, skipped: int,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> dict[str, Any]:
        if status not in {"RUNNING", "SUCCEEDED", "FAILED"}:
            raise ValidationError(f"unexpected status {status!r}", None)
        ok = DAO_FACTORY.get(IInitialDataDao).complete(
            tracker_id, status, inserted, skipped, error, wf_ref_id
        )
        if status == "SUCCEEDED":
            # The workflow path lands here instead of the inline one, and needs the same
            # invalidation -- otherwise a DAG-driven seed is invisible in the portal.
            for name in (CACHE_DOMAINS, CACHE_DATASETS, CACHE_ENDPOINTS, CACHE_MIOS):
                SERVICE_FACTORY.get(IAppCacheService).evict_all(name, settings.tenant_id)
        return {"tracker_id": str(tracker_id), "updated": ok}
