# ADR-015: Endpoints name their configuration; they never hold it

**Status:** Accepted · 2026-09-12

## Decision
`app_endpoint` records **how** to reach a system, never the credentials for doing so.

`config_env` maps a logical key to the *name* of an environment variable:

```json
{"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION",
 "access_key_id": "AKG_AWS_ACCESS_KEY_ID", "secret_access_key": "AKG_AWS_SECRET_ACCESS_KEY"}
```

One row then works in every environment — local, `azure-dev` and `aws-prod` supply
different values for the same names. Nothing secret enters the catalog, so a list API
returning these rows leaks nothing, and a screenshot of the Endpoints page is safe.

Every variable is `AKG_`-prefixed and a CHECK enforces it. The constraint's real job is
catching the common mistake: pasting the secret where the *name* belongs. A real key is
lowercase or mixed and never matches `AKG_[A-Z0-9_]+`.

## Authentication is a deployment fact
The same S3 bucket is reached by a named profile on a laptop, an attached role in EKS, and
keys in CI. That is a property of where the process runs, not of the dataset, so
`auth_mode` carries it: `env_vars`, `aws_profile`, `aws_role`, `azure_cli`,
`azure_managed_identity`, `azure_client_secret`, `gcp_adc`, `anonymous`. `auth_ref` holds
the non-secret selector — a profile name, a tenant id.

`akg_service_core.credentials.probe` reports what this machine can actually do: which AWS
profiles exist in `~/.aws`, whether `az login` left a token, whether an ambient role is
announced in the environment. It reads names and never values.

Two things it deliberately does not do. It does not call IMDS, because a network round trip
inside a health check hangs on a machine with no metadata service. And it does not shell
out to `aws` or `az` — a subprocess per request is slow, and running a CLI whose arguments
derive from stored data is an injection surface for an answer obtainable by reading the
files those tools write. `probe_cli_login` exists for when the CLI's own view is genuinely
needed, with a fixed argv and no shell, and the caller has to ask.

## System endpoints cannot be deleted
The ways this platform reaches storage and databases ship with the product: local
filesystem, S3 three ways, Azure Blob three ways, Postgres local / RDS / Azure, and the
PubMed origin. A dataset location pointing at a deleted endpoint is a build that cannot
run, and the failure appears far from the delete.

Protection is a trigger, not service code, because the catalog is written by migrations, by
psql, and eventually by more than one service — a rule enforced in one caller holds until
the second caller arrives. Deletion is refused, `code` and `tech_stack` are immutable
(renaming an endpoint out from under the locations pointing at it is a delete wearing a
different hat), and `is_system` cannot be cleared, or protection would be one UPDATE away.
Deactivating (`is_active = false`) is the supported way to retire one.

## Passwords for database endpoints
Host, port, database and **username** are connection facts and are stored. The password is
only ever the name of an environment variable. Additional query parameters live in
`options`, which already rejects credential-shaped keys — that is where a password
otherwise gets smuggled in as part of a connection string.
