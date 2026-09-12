# ADR-002: Azure is the only v1 cloud target; AWS follows after stabilisation

**Status:** Accepted · 2026-09-12

## Context
PRD A §4 lists "supporting multiple cloud providers in Version 1" as a non-goal, and both PRDs
target AWS exclusively. The requirement is now Azure first, AWS once Azure is stable, with all
development happening locally at no cloud cost.

## Decision
Azure is the sole v1 cloud target. AWS is a phase-2 target, not a parallel one. The non-goal is
restated: *one cloud at a time; the port layer must not make the second cloud harder.*

Every capability is reached through a port with at least a local adapter and an Azure adapter. An
AWS adapter is written in phase 2 against the same contract tests. Domain code imports no
provider SDK — this was already PRD A §6.1 and PRD B §5.1, and it is what makes the sequence
affordable.

## Consequences
- `config/local.yaml`, `config/azure-dev.yaml`, `config/azure-prod.yaml` now; `aws-*.yaml` in phase 2.
- Contract tests are the gate: an adapter is done when it passes the same suite as the local one.
- Terraform, not Bicep, so phase 2 reuses module structure and CI wiring.
