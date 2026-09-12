"""data_mgmt.imports.import_external_dataset

Register and land a dataset that arrived from outside the platform — a vendor drop, an
uploaded file, a partner feed — as opposed to one we pull from a known source.

The difference from acquisition is who initiates: acquisition pulls from a source we
already recorded, an import lands something that appeared.
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

DAG_ID = "data_mgmt.imports.import_external_dataset"


@dag(
    dag_id=DAG_ID,
    description="Land an externally supplied dataset into a destination endpoint",
    schedule=None,
    start_date=pdt(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "akg", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["akg", "data_mgmt", "import"],
    max_active_runs=4,
)
def import_external_dataset():
    @task
    def read_conf(**context) -> dict[str, Any]:
        conf = require_conf(
            context, "dataset_endpoint_id", "source_uri", "catalog_callback_url"
        )
        return {
            "endpoint_id": conf["dataset_endpoint_id"],
            "source_uri": conf["source_uri"],
            "catalog_url": conf["catalog_callback_url"],
            "trace_id": conf.get("trace_id", ""),
        }

    @task
    def validate_source(cfg: dict[str, Any]) -> dict[str, Any]:
        """Reject a source URI carrying credentials.

        The catalog rejects these at the column, but an import can be handed a URI that
        never goes through the catalog, and a password in dag_run.conf is a password in
        the Airflow UI and in its logs.
        """
        import re

        from airflow.exceptions import AirflowFailException

        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@]*:[^/@]*@", cfg["source_uri"]):
            raise AirflowFailException(
                "source_uri carries credentials; pass a secret reference instead — "
                "dag_run.conf is visible in the Airflow UI and in task logs"
            )
        return {"source_uri": cfg["source_uri"]}

    @task
    def land_files(cfg: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        log.warning("land_files is a stub; nothing was imported")
        return {"bytes": 0, "object_count": 0, "stub": True}

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def report(cfg: dict[str, Any], result: dict[str, Any] | None, **context) -> dict[str, Any]:
        cb = CatalogCallback(cfg["catalog_url"], cfg["trace_id"])
        run_id = context["dag_run"].run_id if context.get("dag_run") else None
        if result is None:
            return cb.report_sync(
                cfg["endpoint_id"], "FAILED",
                error={"detail": "import did not complete"}, wf_ref_id=run_id,
            )
        return cb.report_sync(
            cfg["endpoint_id"], "COMPLETED",
            bytes_written=result.get("bytes", 0),
            object_count=result.get("object_count", 0), wf_ref_id=run_id,
        )

    cfg = read_conf()
    report(cfg, land_files(cfg, validate_source(cfg)))


import_external_dataset()
