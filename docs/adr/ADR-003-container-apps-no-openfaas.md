# ADR-003: Azure Container Apps hosts the services; OpenFaaS is dropped

**Status:** Accepted · 2026-09-12

## Context
Both PRDs mandate OpenFaaS as the function abstraction and explicitly forbid AWS Lambda (the
equivalent Azure prohibition being Azure Functions). OpenFaaS requires Kubernetes, so honouring it
on Azure means an AKS node pool billing continuously. Development must cost nothing and idle cloud
cost must be near zero.

## Decision
Services run on Azure Container Apps with scale-to-zero. Function-shaped work — citation
validation, checksums, alias normalisation, small fan-out — becomes Container Apps Jobs driven by
KEDA rather than OpenFaaS functions. PRD A §6.3 and PRD B M6 are superseded.

The function *eligibility rules* survive unchanged: stateless, short, bounded, no GPU, no
multi-step transaction ownership. Work that outgrows them is promoted to a service, exactly as
before.

## Consequences
- No Kubernetes to operate in v1, and no OpenFaaS control plane.
- Containers stay OCI-standard, so an AKS or EKS move later is a deployment swap, not a rewrite.
- Helm charts are deferred, not forbidden; nothing may depend on Container Apps semantics inside
  domain code.
- Trade-off accepted: we lose OpenFaaS's identical-local-and-cloud function runtime. Jobs are
  exercised locally as plain containers instead.
