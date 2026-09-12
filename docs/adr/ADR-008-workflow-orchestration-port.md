# ADR-008: Orchestration is a port; the execution log is engine-neutral

**Status:** Accepted · 2026-09-12

## Context
The Admin portal must trigger data workflows. Airflow runs them in v1, but Azure Functions,
Azure-hosted Kafka consumers, AWS Step Functions and AWS Lambda are all plausible later
engines for the same logical workflow. The portal must not know which one ran.

## Decision
The Admin portal calls a FastAPI endpoint. That service owns a `WorkflowRunner` port with one
adapter per engine, and writes every invocation to a single engine-neutral table before the
engine is touched.

```
Portals/Admin ──HTTP──▶ Middleware/orchestrator ──▶ WorkflowRunner (port)
                              │                         ├── AirflowAdapter        (v1)
                              │                         ├── ContainerAppsJobAdapter (v1)
                              │                         ├── AzureFunctionsAdapter  (later)
                              │                         ├── StepFunctionsAdapter   (phase 2)
                              │                         └── LambdaAdapter          (phase 2)
                              ▼
                     workflow_exec_log  (Postgres, JSONB)
```

The row is written **before** the engine is invoked, in state `PENDING`, and carries the
`trace_id` that the portal request minted. The engine's own identifier lands in `wf_ref_id`
once the engine returns it — `dag_run_id` for Airflow, an execution ARN for Step Functions, a
request id for Lambda. A row with no `wf_ref_id` and a stale `created_at` is therefore a
detectable submit failure rather than a silent one.

`(tech_stack, wf_ref_id)` is unique, so a retried submit cannot log the same engine execution
twice.

## Naming
The owner specified `airflow_exec_log`. The table is `workflow_exec_log` because it records
executions from every engine and the `tech_stack` column is what proves it; a table named after
one engine misleads the day a second appears. `airflow_exec_log` exists as a view filtered to
`tech_stack = 'airflow'`, so the original name still resolves and is in fact more accurate as a
view than it would be as the table.

## Relationship to ADR-003
ADR-003 drops OpenFaaS and forbids building the function tier *on* Azure Functions or Lambda as
the mandated abstraction. Listing them as adapter values does not reopen that: the port is the
abstraction, and an adapter is an implementation detail selected by config. v1 implements
`airflow` and `container_apps_job` only.

## Consequences
- The portal has one contract regardless of engine, and switching engines is a config change plus
  an adapter, not a portal change.
- Every workflow invocation is auditable in one place, with the same `trace_id` as the answer
  path, so a data build and a query that used its artifacts are correlatable.
- JSONB for `input_data` / `output_data` keeps the table stable as workflow signatures change;
  the cost is that input shape is validated by the contracts package rather than by the database.
