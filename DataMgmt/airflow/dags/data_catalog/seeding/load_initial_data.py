"""data_catalog.seeding.load_initial_data

Populate reference content into a blank database: purposes, domains, endpoints, datasets,
workflows. Triggered from Administration → Initial Data, one entity per run.

Two properties the Administration screen depends on:

  * Every insert is conflict-tolerant, so a repeat changes nothing. The tracker refuses a
    second load anyway, but the DAG does not rely on that being true -- a DAG that only
    works when called correctly is a DAG that breaks when it is called twice.
  * The run reports inserted and skipped separately, because "loaded 13" and "loaded 0,
    13 already present" are different facts that look identical if you only report success.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from airflow.decorators import dag, task
from airflow.utils.trigger_rule import TriggerRule
from akg_common import CatalogCallback, require_conf
from pendulum import datetime as pdt

log = logging.getLogger(__name__)

DAG_ID = "data_catalog.seeding.load_initial_data"

#: Loading order, mirroring catalog.initial_data_status.load_order. Kept here only for
#: validation; the catalog is the authority and refuses an out-of-order load itself.
ORDER = {"purposes": 1, "domains": 2, "endpoints": 3, "datasets": 4, "workflows": 5}


@dag(
    dag_id=DAG_ID,
    description="Load reference content for one entity into a blank catalog",
    schedule=None,
    start_date=pdt(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "akg", "retries": 1, "retry_delay": timedelta(minutes=1)},
    tags=["akg", "data_catalog", "seeding"],
    max_active_runs=1,
)
def load_initial_data():
    @task
    def read_conf(**context) -> dict[str, Any]:
        conf = require_conf(context, "entity", "tracker_id", "catalog_callback_url")
        entity = conf["entity"]
        if entity not in ORDER:
            from airflow.exceptions import AirflowFailException

            raise AirflowFailException(
                f"unknown entity {entity!r}; expected one of {sorted(ORDER)}"
            )
        return {
            "entity": entity,
            "tracker_id": conf["tracker_id"],
            "catalog_url": conf["catalog_callback_url"],
            "trace_id": conf.get("trace_id", ""),
        }

    @task
    def seed(cfg: dict[str, Any]) -> dict[str, Any]:
        """Insert the reference rows for this entity.

        A stub: it reports zero inserted, which the Administration screen shows honestly
        as a load that added nothing. Replace per entity with real inserts through the
        catalog's own APIs rather than direct SQL, so the same validation applies to seed
        data as to anything else.
        """
        log.warning("seed is a stub for entity=%s; no rows were inserted", cfg["entity"])
        return {"inserted": 0, "skipped": 0, "stub": True}

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def report(cfg: dict[str, Any], result: dict[str, Any] | None, **context) -> dict[str, Any]:
        cb = CatalogCallback(cfg["catalog_url"], cfg["trace_id"])
        run_id = context["dag_run"].run_id if context.get("dag_run") else None
        payload: dict[str, Any] = (
            {"status": "FAILED", "error": {"detail": "seeding task did not complete"}}
            if result is None
            else {"status": "SUCCEEDED", "inserted": result.get("inserted", 0),
                  "skipped": result.get("skipped", 0)}
        )
        payload["wf_ref_id"] = run_id
        # Always reports, success or failure: a tracker row left RUNNING blocks every
        # future load of that entity, permanently.
        return cb.post(
            f"/api/v1/admin/initial-data/{cfg['tracker_id']}/status", payload
        )

    cfg = read_conf()
    report(cfg, seed(cfg))


load_initial_data()
