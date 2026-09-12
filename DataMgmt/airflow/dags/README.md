# Airflow DAGs

Mounted read-only into the Airflow container at `/opt/airflow/dags` by
`CICD/Local/Airflow/docker-compose.yml`; `../plugins` is mounted alongside and is on
`sys.path`, which is why shared helpers live there rather than here.

## Layout: service, then area

```
dags/
  data_mgmt/
    acquisition/   pull a dataset from its source into a destination
    exports/       publish a curated copy outward
    imports/       land something that arrived from outside
  data_catalog/
    maintenance/   housekeeping the catalog cannot do to itself
plugins/
  akg_common/      CatalogCallback, require_conf — importable, never scanned as DAGs
```

One folder per owning microservice, then one per area. With a handful of DAGs a flat
folder is fine; with several services it stops being obvious who owns what, and
`dag_id` is globally unique in Airflow, so two services are one `export_dataset` away
from a collision.

## `dag_id` mirrors the path

`<service>.<area>.<name>` — `data_mgmt.acquisition.acquire_dataset_endpoint`. The id in
the Airflow UI tells you which service triggered it and which file to open, and the
namespace makes a collision between two services impossible rather than unlikely.

## Registry

| dag_id | Trigger | Purpose |
|---|---|---|
| `data_mgmt.acquisition.acquire_dataset_endpoint` | data-mgmt API | Copy a dataset from source to destination, then report to the catalog |
| `data_mgmt.exports.export_dataset_endpoint` | data-mgmt API | Publish a curated copy; refuses if the source is not `available` |
| `data_mgmt.imports.import_external_dataset` | data-mgmt API | Land an externally supplied dataset; rejects a `source_uri` carrying credentials |
| `data_catalog.maintenance.release_stuck_syncs` | hourly schedule | Fail endpoints whose run never reported back |

## Conventions

- **Triggered, not scheduled.** These run because a service asked: `schedule=None` and the
  caller supplies `dag_run.conf`. `release_stuck_syncs` is the deliberate exception.
- **Validate `dag_run.conf` first.** `require_conf` fails the run rather than letting a
  missing key become a `None` that acquires the wrong thing.
- **Report with `trigger_rule=ALL_DONE`.** A DAG that reports only on success leaves the
  endpoint `RUNNING`, and the claim that makes concurrency safe then means nothing can ever
  claim it again. That is what `release_stuck_syncs` exists to clean up.
- **The catalog owns locations and availability.** A DAG is told *which* endpoint, not
  where it points, and it reports what it moved rather than asserting the data is
  available — a run that completes having moved zero bytes leaves the endpoint unavailable.
- **`catalog_callback_url` comes from conf.** Inside Compose it is a service name; a DAG
  hard-coding `localhost` would be calling its own container.
- **Airflow orchestrates, it does not compute.** Heavy work belongs in a containerised job
  the DAG launches, so the scheduler never becomes the bottleneck.
- **No credentials in `dag_run.conf`.** It is visible in the Airflow UI and in task logs.
  Pass a secret reference; the import DAG rejects a URI with userinfo for this reason.
