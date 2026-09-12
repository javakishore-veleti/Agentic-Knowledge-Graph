"""dag_run.conf validation.

A triggered DAG's conf is its only input. Reading a missing key as None and continuing is
how a DAG ends up acquiring the wrong thing, or finishing with nothing to report back to.
"""

from __future__ import annotations

from typing import Any

from airflow.exceptions import AirflowFailException


def require_conf(context: dict[str, Any], *keys: str) -> dict[str, Any]:
    run = context.get("dag_run")
    conf: dict[str, Any] = (run.conf or {}) if run else {}
    missing = [k for k in keys if not conf.get(k)]
    if missing:
        raise AirflowFailException(
            f"dag_run.conf is missing {missing}; this DAG is triggered by a service and "
            f"cannot run without them"
        )
    return conf
