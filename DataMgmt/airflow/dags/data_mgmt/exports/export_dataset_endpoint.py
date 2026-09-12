"""data_mgmt.exports.export_dataset_endpoint

Publish a curated dataset copy to an export destination for downstream consumers.

Separate from acquisition on purpose: acquisition brings data in and may be retried
freely, while an export is outward-facing and re-publishing has consequences for whoever
already consumed it.
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

DAG_ID = "data_mgmt.exports.export_dataset_endpoint"


@dag(
    dag_id=DAG_ID,
    description="Publish a curated dataset copy to an export endpoint",
    schedule=None,
    start_date=pdt(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "akg", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["akg", "data_mgmt", "export"],
    max_active_runs=4,
)
def export_dataset_endpoint():
    @task
    def read_conf(**context) -> dict[str, Any]:
        conf = require_conf(
            context, "dataset_endpoint_id", "target_endpoint_id", "catalog_callback_url"
        )
        return {
            "source_endpoint_id": conf["dataset_endpoint_id"],
            "target_endpoint_id": conf["target_endpoint_id"],
            "catalog_url": conf["catalog_callback_url"],
            "trace_id": conf.get("trace_id", ""),
            "format": conf.get("format", "parquet"),
        }

    @task
    def verify_source_available(cfg: dict[str, Any]) -> dict[str, Any]:
        """Refuse to export data that is not there.

        Exporting from an endpoint that never completed its acquisition publishes an empty
        or partial dataset to consumers, which is worse than publishing nothing.
        """
        from airflow.exceptions import AirflowFailException

        ep = CatalogCallback(cfg["catalog_url"], cfg["trace_id"]).dataset_endpoint(
            cfg["source_endpoint_id"]
        )
        if ep.get("state") != "available":
            raise AirflowFailException(
                f"source endpoint state is {ep.get('state')!r}, not 'available'; "
                f"refusing to export data that has not arrived"
            )
        return ep

    @task
    def write_export(cfg: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
        log.warning("write_export is a stub; nothing was published")
        return {"bytes": 0, "object_count": 0, "stub": True}

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def report(cfg: dict[str, Any], result: dict[str, Any] | None, **context) -> dict[str, Any]:
        cb = CatalogCallback(cfg["catalog_url"], cfg["trace_id"])
        run_id = context["dag_run"].run_id if context.get("dag_run") else None
        if result is None:
            return cb.report_sync(
                cfg["target_endpoint_id"], "FAILED",
                error={"detail": "export did not complete"}, wf_ref_id=run_id,
            )
        return cb.report_sync(
            cfg["target_endpoint_id"], "COMPLETED",
            bytes_written=result.get("bytes", 0),
            object_count=result.get("object_count", 0), wf_ref_id=run_id,
        )

    cfg = read_conf()
    report(cfg, write_export(cfg, verify_source_available(cfg)))


export_dataset_endpoint()
