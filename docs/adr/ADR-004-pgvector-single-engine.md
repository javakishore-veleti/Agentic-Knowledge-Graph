# ADR-004: One Postgres engine for relational and vector; pgvector is the retrieval backend

**Status:** Accepted · 2026-09-12

## Context
PRD B M9 defaults to OpenSearch k-NN on both targets. On Azure the managed analogue is AI Search,
which has no faithful local equivalent, so local dev would exercise a different engine from
production — the parity failure ADR-002 exists to prevent. PRD A already defines pgvector as a
supported vector port.

## Decision
Postgres with pgvector is the vector backend in every environment: a `postgres` container locally,
Postgres Flexible Server on Azure, Aurora Postgres in phase 2. One engine serves both the
service-owned relational stores and dense retrieval, behind a `VectorRepository` port.

A `memmap-exact` backend is still required for eval oracle runs (PRD B M9), because an approximate
index must never be the thing an oracle arm measures.

## Consequences
- Hybrid retrieval is our own BM25-plus-vector fusion rather than a managed semantic ranker. The
  fusion weights become swept constants, which PRD B §C2 requires anyway.
- Gold-in-top-16 ≥ 95% (PRD B M9 acceptance) must be met by pgvector or this ADR is revisited.
- An `AiSearchAdapter` may be added later to prove the port; it is not v1 scope.
- No separate search service to provision, secure, or pay for.
