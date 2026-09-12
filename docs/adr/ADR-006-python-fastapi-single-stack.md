# ADR-006: Python and FastAPI for every service

**Status:** Accepted · 2026-09-12

## Context
PRD A §6.4 mandates Spring Boot for middleware with Python only for AI services. PRD B leaves
language open but specifies a Pydantic contracts package. This repo's scaffold is Python 3.13, the
PoC notebook is Python, and the upstream reference implementation is Python.

## Decision
One language: Python 3.13, FastAPI for HTTP services, Pydantic v2 for contracts. PRD A's Spring
Boot mandate is superseded.

## Consequences
- The contracts package is importable by every service and by the eval harness, so schema drift
  between a Java DTO and a Python model cannot happen.
- Numeric code (CSR traversal, fusion, calibration) shares one runtime with the serving path, so
  the eval harness and the services cannot disagree about scoring.
- A single CI lane instead of A §18.1's separate `pr-java` and `pr-python` workflows.
- Trade-off: no JVM ecosystem. Accepted — nothing in the design needs it.
