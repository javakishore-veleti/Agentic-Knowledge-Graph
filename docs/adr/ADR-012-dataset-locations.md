# ADR-012: A dataset's source and its destinations are one table, separated by role

**Status:** Accepted · 2026-09-12

## Context
A dataset has a root location it comes *from* — a Kaggle URL, the PubMed FTP baseline, a
vendor HTTPS endpoint — and one or more places it is stored *to*: S3, Azure Blob, GCS,
Postgres, MySQL, a file server, a local path. A MIO reads one specific copy, not "the
dataset" in the abstract, and which copy it read matters for reproducing a build.

## Decision
`catalog.dataset_endpoint` holds both, distinguished by `role`:

| role | meaning | `app_endpoint_id` |
|---|---|---|
| `source` | where it came from, often outside our estate | nullable |
| `landing` | raw copy as acquired | required |
| `curated` | parsed / normalised copy | required |
| `export` | published for downstream consumers | required |

A destination must name a registered `app_endpoint`, because you cannot store into a
system that has no host, no credentials reference and no owner. A source frequently
cannot: nobody registers Kaggle as an app endpoint. That asymmetry is the `CHECK`, not a
convention.

`app_endpoint` remains *the system* — host, port, database, Key Vault reference.
`dataset_endpoint` is *the place within it* — bucket and prefix, schema and table,
container and path. Splitting them means one registered Postgres serves many datasets
without repeating its connection details, and rotating a secret touches one row.

`mio_dataset.dataset_endpoint_id` records which copy a MIO reads. Null means "the primary
for its role", so existing rows keep working, but a build that pinned a specific copy can
say so.

## Credentials never appear in a URI
`postgres://user:hunter2@host/db` is a password in a catalog column that list APIs return
and portals render. A `CHECK` rejects any URI carrying userinfo before the host. The
connection secret lives where it already lived: the `app_endpoint`'s `secret_ref`.

## One primary per role
A partial unique index allows exactly one primary `dataset_endpoint` per
`(dataset_id, role)`. Without it "the curated copy" is ambiguous the moment a second
appears, and a build would silently pick whichever the query ordered first.

## Consequences
- The DataSets page shows where each dataset lives, not just that it exists.
- Choosing a dataset for a MIO becomes choosing a dataset *and a location*.
- `dataset_without_source` flags a dataset nobody can rebuild from, which is otherwise
  invisible until a rebuild is attempted.
