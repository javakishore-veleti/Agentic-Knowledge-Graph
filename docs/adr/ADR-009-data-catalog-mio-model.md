# ADR-009: The catalog is domain → dataset → MIO → data_instance → exec

**Status:** Accepted · 2026-09-12

## Context
The platform needs to answer "what data do we have, what was produced from it, by which
run, and where does it live". Until now the Admin portal treated a *dataset* as both the
source corpus and the produced artifact, which conflates two things with different
lifecycles: a source version is immutable once acquired, while a produced artifact is
rebuilt repeatedly.

## Decision
Five levels, each owning one idea.

```
domain                     biomedical, enterprise
  └── dataset              source data at a source_version (immutable once acquired)
        └── mio            Managed Informational Object -- a project-like managed
            │              artifact built from one or more datasets. Carries the
            │              produced thing's shape: technology, document and edge
            │              counts, validations, size, state.
            ├── workflows  the workflows that build and maintain it
            └── data_instance        historical | realtime | cdc
                  └── data_instance_exec    one run
```

A MIO may **generate other MIOs**. That edge is recorded in `mio_lineage` together with
the `data_instance_exec` that produced it, so provenance answers "which run created this"
rather than only "what came from what".

`app_endpoint` holds where a technology actually lives. Several endpoints may exist for
one technology (a local Postgres and an Azure Postgres; two OpenSearch clusters), so
nothing is keyed on technology alone.

## Four points this pins down

**Credentials never enter the catalog.** `app_endpoint` stores host, port, database and
options, plus `secret_ref` naming a Key Vault entry. It does not store passwords. A
catalog row is read by list APIs, rendered in a portal, and pasted into screenshots; a
secret in that path is a secret that has leaked. The API response model has no field
capable of carrying one.

**CDC gets exactly one instance per MIO, enforced.** Change data capture is a continuous
stream, not a series of batches: giving it one instance per change would produce millions
of near-empty `data_instance` rows and bury the historical and realtime instances that
matter. A partial unique index permits at most one `cdc` instance per MIO, and its id is
derived (`<mio_id>:cdc`) rather than random, so a consumer can address it without a
lookup. Historical and realtime instances stay one-per-run.

**`wf_execs_json` is a cache, not the record.** `wf_exec_log.data_instance_exec_id` is the
foreign key that makes "which workflows ran for this execution" answerable by join, with
integrity. The JSON list is kept because the portal wants one row read, and
`data_instance_exec_drift` recounts it against `wf_exec_log` — the same discipline the
`wf_batch` counters already follow. A cache nobody checks is a cache that drifts.

**`input_data_json` / `output_data_json` stay JSONB.** Input and output shapes differ per
technology and will change faster than migrations can follow. The cost is that
"which executions wrote to this endpoint" cannot be a plain join, so
`data_instance_exec_endpoint` records that one relationship explicitly while the payload
detail stays in JSON.

## Consequences
- The Admin DataSets page is wrong as built: it shows counts, validations and state on the
  dataset. Those move to the MIO, and DataSets becomes the source-version view.
- Postgres, per ADR-004. MySQL was considered and rejected: it would be a second engine
  and would give up pgvector.
- SQLAlchemy is the ORM, with the schema owned by SQL migrations rather than generated
  from models, so the constraints above exist in the database and not only in Python.
