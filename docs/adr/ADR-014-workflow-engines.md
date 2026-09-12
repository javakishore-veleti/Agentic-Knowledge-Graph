# ADR-014: Engines are a closed set, and execution model decides what the portal offers

**Status:** Accepted · 2026-09-12

## Context
Workflows will run on many engines: Airflow, Step Functions, EMR, Glue, Batch, Data
Factory, Logic Apps, Lambda, Databricks, Kinesis, Kafka consumers, Spark Streaming, BPMN
engines, and plain custom APIs. Two problems followed.

`default_tech_stack` had no constraint, so the column accepted any string and a typo would
surface as a portal offering a button for an engine no adapter implements.

More importantly, those engines do not share one notion of "run".

## Decision
Nineteen engines, as a closed set enforced by CHECK on both `catalog.workflow` and
`orchestration.wf_exec_log`, each belonging to one of three execution models:

| Model | Engines | What the portal offers |
|---|---|---|
| `triggered_run` | Airflow, Container Apps Jobs, Azure Functions, Data Factory, Logic Apps, Step Functions, Lambda, EMR, Glue, Batch, Databricks, custom API | **Invoke** |
| `continuous` | Kafka consumers (Azure/AWS), Kinesis, Event Hubs, Spark Streaming | Health and lag. **Never invoke** |
| `human_process` | Camunda, Flowable | Open the instance; completion waits on people |

Invoking a continuous engine would write a `PENDING` execution that never completes,
filling the log with rows that can only be closed by hand. This is the same distinction
already made for CDC data instances (ADR-009): a continuous thing is not a series of runs,
and modelling it as one buries everything else.

`catalog.workflow_invocable` is the view the portal reads for attachable, runnable
workflows. `wf_exec_log_model_mismatch` flags execution rows written against a continuous
engine, which is a modelling error rather than a data error.

## Consequences
- Adding an engine is a migration plus an adapter, and the database rejects it until the
  migration lands — which is the right order.
- The Admin portal disables invoke by execution model rather than by engine name, so a new
  streaming engine is handled without touching the UI.
- `TechStack.invocable` is available to every service through the contracts package, so the
  rule is not re-implemented per caller.
