# ADR-001: PRD B is authoritative; PRD A contributes selected sections

**Status:** Accepted · 2026-09-12

## Context
Two PRDs described the same product with conflicting designs. `PRD-agentic-knowledge-graph-platform.md`
("B") specifies CSR-on-memmap with no graph database, 7 middleware services, and module briefs
M0–M17. `Agentic-Knowledge-Graph-Platform-PRD.md` ("A") specifies JanusGraph/Neptune, 13 middleware
services, and Spring Boot. The upstream reference implementation and this repo's PoC both use
CSR-on-memmap, which A lists as an explicit non-goal.

## Decision
PRD B is the authoritative design. Three sections of PRD A are retained because they are better:

- A §6.5 / §13.1 storage **ports** table — B hard-codes an S3-compatible client, which breaks on Azure.
- A §21 release-manifest publication protocol — B's per-artifact pinning does not prevent mixing
  incompatible graph/index/catalog versions.
- A §27 ADR list — B has no decision record requirement.

## Consequences
- No graph database in any environment. The most expensive component of A disappears.
- Neptune, Cosmos DB Gremlin, and JanusGraph are out of scope.
- A's 13-service split collapses to B's 7.
- A's Spring Boot mandate is superseded by ADR-006.
