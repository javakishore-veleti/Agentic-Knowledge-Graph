"""data_mgmt.acquisition.acquire_dataset_endpoint

Copy one dataset from its source location into one destination endpoint.

Triggered by the data-mgmt service, never scheduled. The service has already claimed the
endpoint, so this DAG holds the claim and owes exactly two things: move the data, and
report the outcome. A run that ends without reporting leaves the endpoint RUNNING and
nothing can claim it again — which is why the reporting task uses ALL_DONE.
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

DAG_ID = "data_mgmt.acquisition.acquire_dataset_endpoint"


@dag(
    dag_id=DAG_ID,
    description="Copy a dataset from its source to a destination endpoint",
    schedule=None,
    start_date=pdt(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "akg", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["akg", "data_mgmt", "acquisition"],
    max_active_runs=8,
)
def acquire_dataset_endpoint():
    @task
    def read_conf(**context) -> dict[str, Any]:
        conf = require_conf(context, "dataset_endpoint_id", "catalog_callback_url")
        return {
            "endpoint_id": conf["dataset_endpoint_id"],
            "catalog_url": conf["catalog_callback_url"],
            "trace_id": conf.get("trace_id", ""),
        }

    @task
    def fetch_endpoint(cfg: dict[str, Any]) -> dict[str, Any]:
        """The DAG is told which endpoint, not where it points.

        The catalog is the authority on locations; copying them into dag_run.conf would
        let the two disagree.
        """
        ep = CatalogCallback(cfg["catalog_url"], cfg["trace_id"]).dataset_endpoint(
            cfg["endpoint_id"]
        )
        log.info("acquiring into %s (%s)", ep.get("uri"), ep.get("location_kind"))
        return ep

    @task
    def copy_to_destination(endpoint: dict[str, Any]) -> dict[str, Any]:
        """The transfer itself.

        A stub: it reports zero bytes, which the catalog deliberately reads as "the run
        finished but the data did not arrive" rather than marking the endpoint available.
        Replace per location_kind (s3, azure_blob, gcs, postgres, file_server) with a real
        transfer returning what it actually wrote.
        """
        kind = endpoint.get("location_kind")
        log.warning("copy_to_destination is a stub for kind=%s; no data moved", kind)
        return {"bytes": 0, "object_count": 0, "stub": True}

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def report(cfg: dict[str, Any], result: dict[str, Any] | None, **context) -> dict[str, Any]:
        cb = CatalogCallback(cfg["catalog_url"], cfg["trace_id"])
        run_id = context["dag_run"].run_id if context.get("dag_run") else None
        if result is None:
            return cb.report_sync(
                cfg["endpoint_id"], "FAILED",
                error={"detail": "acquisition task did not complete"}, wf_ref_id=run_id,
            )
        return cb.report_sync(
            cfg["endpoint_id"], "COMPLETED",
            bytes_written=result.get("bytes", 0),
            object_count=result.get("object_count", 0),
            wf_ref_id=run_id,
        )

    cfg = read_conf()
    report(cfg, copy_to_destination(fetch_endpoint(cfg)))


acquire_dataset_endpoint()
