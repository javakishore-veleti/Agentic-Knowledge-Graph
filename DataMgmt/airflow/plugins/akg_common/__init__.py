"""Helpers shared by every AKG DAG.

Lives in plugins/ rather than dags/ because Airflow puts the plugins folder on sys.path
and does not scan it for DAGs — a helper module in dags/ gets parsed on every scan and
risks being mistaken for a DAG file.
"""

from .catalog import CatalogCallback
from .dag_conf import require_conf

__all__ = ["CatalogCallback", "require_conf"]
