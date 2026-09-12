# ADR-010: Every middleware API follows api → service → dao, over DTOs only

**Status:** Accepted · 2026-09-12

## Context
Services will be written by different agents at different times. Without one shape, each
arrives with its own idea of where validation lives, what crosses a boundary, and how a
dependency is obtained. The cost shows up later, when a change has to be made in five
services that are only superficially alike.

## Decision

### Packages
Every service under `Middleware/<name>/src/<pkg>/` has exactly these:

| Package | Holds | May import |
|---|---|---|
| `api` | HTTP routers. Thin: bind, delegate, return. | `dtos`, `common`, service **interfaces** |
| `service` | Business logic, one interface + one impl per capability | `dtos`, `common`, dao **interfaces**, `integration` |
| `dao` | Persistence. The only package that knows SQL or the ORM | `dtos`, `common`, `entities` |
| `integration` | Clients for other services | `dtos`, `common` |
| `dtos` | Ctx / Req / Resp objects | `common` |
| `common` | Factories, context base, errors, paging | nothing in the service |
| `entities` | ORM mappings. **DAO-private.** | `common` |

`api` must not import `dao`, and nothing outside `dao` may import `entities`. The
dependency test in `tests/test_layering.py` enforces both by reading imports, so the rule
survives the next contributor.

### DTOs only, end to end
An ORM entity never leaves the `dao` package. The DAO maps rows to DTOs before returning.
A lazily-loaded relationship that escapes to the API layer becomes a query in the
serializer, and an entity in a response body couples the wire format to the schema — both
are discovered in production rather than in review.

### Three classes per API
Each API operation defines exactly three, named for the noun or verb:

- `<Op>Req` — every input parameter. Handlers take one `Req`, never loose arguments, so
  adding an input changes one class rather than every signature down the chain.
- `<Op>Resp` — the response body.
- `<Op>Ctx` — the request-scoped context: it carries the `Req`, `trace_id`, `tenant_id`
  and `env`, and receives the `Resp`. The `Ctx` is what travels api → service → dao, so
  the trace id reaches the persistence layer without a parameter being threaded through
  every call.

### Interfaces, and lookup by interface
Every service and DAO is an interface (`IXxx`, an ABC) with an implementation (`XxxImpl`).
Callers depend on the interface and never construct the implementation.

Two factories, one per boundary:

- `SERVICE_FACTORY` — api → service
- `DAO_FACTORY` — service → dao

Both resolve by interface type. Registration happens once in `bootstrap.py`, which is the
only module that names both an interface and its implementation, so swapping an
implementation is a one-line change there.

## Consequences
- More files per endpoint than idiomatic Python would use. Accepted deliberately: uniformity
  across services is worth more here than brevity in any one of them.
- The database session lives inside the DAO implementation, injected at registration. It is
  never a field on a `Ctx`, because that would put a SQLAlchemy object into a DTO and break
  the rule above.
- `data-catalog` is the reference implementation. New services copy its layout.
