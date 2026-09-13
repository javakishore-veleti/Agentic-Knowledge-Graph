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
from akg_common.transfer import DEFAULT_MAX_FILES, download
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
            # A cap on how much one button press downloads; see transfer.DEFAULT_MAX_FILES.
            "max_files": conf.get("max_files"),
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
    def copy_to_destination(endpoint: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
        """The transfer itself.

        Raises rather than returning zero bytes when it cannot copy: `report` runs on
        ALL_DONE and turns a missing result into FAILED, so an unimplemented destination
        leaves the endpoint claimable again instead of marked available with nothing
        behind it.
        """
        source_uri = endpoint.get("source_uri")
        if not source_uri:
            raise ValueError(
                "the catalog returned no source location for this dataset; "
                "there is nothing to download from"
            )
        result = download(
            source_uri,
            endpoint["uri"],
            endpoint.get("location_kind", ""),
            max_files=int(cfg.get("max_files") or DEFAULT_MAX_FILES),
        )
        log.info("wrote %d file(s), %d bytes: %s",
                 result.object_count, result.bytes, ", ".join(result.files))
        return {"bytes": result.bytes, "object_count": result.object_count}

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
    report(cfg, copy_to_destination(fetch_endpoint(cfg), cfg))


acquire_dataset_endpoint()
