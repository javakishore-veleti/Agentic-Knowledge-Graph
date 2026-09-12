# ADR-013: Acquisition is claimed, asynchronous, and reports back

**Status:** Accepted · 2026-09-12

## Decision
A dataset is copied from its source into a destination by the `data-mgmt` service, which
holds no database: the catalog owns dataset state, Airflow owns execution.

```
Admin → data-mgmt  POST /dataset-endpoints/{id}/acquire
                        │
                        ├─ catalog: claim (decision + transition in ONE statement)
                        │     refused → started=false, reason=already_available   ← the point
                        │
                        └─ Airflow: trigger DAG, return immediately
                                       │
        catalog ← POST /sync-status ───┘   (DAG reports its own outcome)
```

## Do not re-download what we already have
The check and the state change are one `UPDATE`. A service that reads "not available" and
then writes has a window where a second caller reads the same thing, and both start a DAG
against one destination. `catalog.claim_dataset_endpoint_sync` returns a row to exactly one
caller; everyone else is told why not — `already_available`, `already_running`,
`not_found`. A refused claim is a **200 with `started=false`**, not an error: an idempotent
caller should not have to parse a failure to learn its data is already there. `force`
re-acquires deliberately.

## Two status axes, not one
`state` answers *is the data there* — `declared | syncing | available | stale | failed`.
`sync_wf_status` answers *did the run finish* — `RUNNING | COMPLETED | FAILED | CANCELLED`.

Collapsing them loses real cases. A run can COMPLETE having written nothing, and a refresh
can run over data that is still perfectly readable. So the catalog *derives* availability
rather than trusting the caller: **COMPLETED with zero bytes leaves the endpoint
unavailable**, because the run finishing and the data arriving are different facts.

## A run that never reports back
The claim that makes concurrency safe is also what deadlocks an endpoint when a DAG is
killed: nothing else will ever claim it. Three things address it — the DAG reports with
`trigger_rule=ALL_DONE` so failure still reports; data-mgmt releases the claim itself if
the Airflow submit fails after claiming; and `data_catalog.maintenance.release_stuck_syncs`
sweeps hourly over `dataset_endpoint_stuck_sync`.

## Credentials
A URI is rejected before the database, not only by the `CHECK`. A constraint violation
arrives as a driver error quoting the whole failing row, so a rejected
`postgres://user:password@host/db` would put that password into the exception text and into
the log line written to complain about it. Validation happens in the service, and every
message about a bad URI goes through `redact_uri`.

The import DAG applies the same rule to `dag_run.conf`, which is visible in the Airflow UI
and in task logs.

## Known gap
`POST /sync-status` mutates dataset state from outside the service and is unauthenticated,
because nothing in the stack authenticates yet. Before it is reachable beyond the local
network it needs service-to-service auth: an open endpoint that can mark data "available"
is an open endpoint that can make a build read nothing.
