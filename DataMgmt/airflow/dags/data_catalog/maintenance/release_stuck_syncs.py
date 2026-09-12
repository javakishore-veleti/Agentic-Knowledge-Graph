"""data_catalog.maintenance.release_stuck_syncs

Release dataset endpoints left RUNNING by a run that died without reporting.

The only scheduled DAG here. It exists because the claim that makes acquisition safe under
concurrency is also what deadlocks an endpoint when a DAG is killed: nothing else will ever
claim it. `catalog.dataset_endpoint_stuck_sync` is the query; this acts on it.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from airflow.decorators import dag, task
from akg_common import CatalogCallback
from pendulum import datetime as pdt

log = logging.getLogger(__name__)

DAG_ID = "data_catalog.maintenance.release_stuck_syncs"
CATALOG_URL = "http://akg-data-catalog:8001"


@dag(
    dag_id=DAG_ID,
    description="Fail dataset endpoints whose acquisition never reported back",
    schedule="0 * * * *",
    start_date=pdt(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "akg", "retries": 0},
    tags=["akg", "data_catalog", "maintenance"],
    max_active_runs=1,
)
def release_stuck_syncs():
    @task
    def find_and_release(**context) -> dict[str, Any]:
        conf = (context["dag_run"].conf or {}) if context.get("dag_run") else {}
        cb = CatalogCallback(conf.get("catalog_callback_url", CATALOG_URL), "stuck-sweeper")
        stuck = cb.get("/api/v1/dataset-endpoints/stuck").get("items", [])
        released = 0
        for row in stuck:
            cb.report_sync(
                row["dataset_endpoint_id"], "FAILED",
                error={"detail": "run never reported back; released by the sweeper",
                       "started_at": row.get("sync_started_at")},
            )
            released += 1
        log.info("released %s stuck acquisition(s)", released)
        return {"released": released}

    find_and_release()


release_stuck_syncs()
