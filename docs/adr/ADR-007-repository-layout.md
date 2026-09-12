# ADR-007: Repository layout, Angular portals, PySpark in DataMgmt

**Status:** Accepted · 2026-09-12

## Context
PRD B §4 specifies a lowercase layout (`platform/`, `middleware/`, `etl/`, `portals/`). The
owner specified a different one, in PRD A's capitalised idiom, and named the local-stack
entry points explicitly.

## Decision
Layout is as follows. PRD B §4 is superseded; PRD A §8 is the closest ancestor.

```
CICD/
  Local/                    docker-all-up.sh · docker-all-down.sh · all-status.sh
    Postgres/ Kafka/ Airflow/ Azurite/ Redis/ Otel/
  Azure/                    Terraform for the Azure target (ADR-002)
  AWS/                      phase 2, same module structure
Middleware/                 FastAPI API services, one directory per service
DataMgmt/
  airflow/dags              orchestration only; jobs run as containers
  pyspark/                  bulk parse, ontology join, embedding fan-out
  adapters/                 pubmed (reference) · generic-extraction
  synthetic/                seed and synthetic corpora for local dev
Portals/Admin  Portals/Customer     Angular
Contracts/                  OpenAPI · AsyncAPI · exported JSON Schema
Libraries/python/akg-contracts      the importable Pydantic package
Evaluation/                 harness · datasets · reports
docs/adr/                   decision records
.github/workflows/          must stay at repo root; these call into CICD/
```

Three points this pins down:

- **`.github/workflows/` stays at the repo root** because GitHub Actions will not discover
  workflows elsewhere. The workflows are thin and call scripts under `CICD/`, so deployment
  logic stays runnable by hand and is not locked inside a CI product.
- **Angular** for both portals, confirming PRD A §6.4 over PRD B's unspecified "web app".
- **PySpark** enters `DataMgmt/pyspark/` for the bulk path. Neither PRD mentioned Spark; the
  reference study did the whole 40M parse single-box. Spark is justified only for the
  parse / ontology-join / embedding fan-out, and Airflow invokes those as containerised jobs.
  It must not appear in the serving path, where the CSR store's whole point is microsecond
  in-process traversal.

## Consequences
- The contracts package moves to `Libraries/python/akg-contracts` and stays the one thing every
  service and the eval harness import (ADR-006).
- Two runtimes in the repo: Python for services and data, TypeScript/Angular for portals. CI gets
  a lane each.
- Local stack is script-driven, not a single compose file, so individual tiers can be brought up
  alone — which is PRD A §12.2's profile idea in a different shape.
