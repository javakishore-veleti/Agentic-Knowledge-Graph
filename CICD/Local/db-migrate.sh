#!/usr/bin/env bash
#
# STATUS: not yet wired into stack-up.sh. One blocker remains.
#
# Liquibase fails on changeset 003 with: syntax error at or near "$1".
# The cause is JDBC, not the SQL: migration 003 uses Postgres's JSONB key-exists
# operator, `options ?| array[...]`, and the driver reads `?` as a bind-parameter
# placeholder and sends it as $1. Two ways out, both mechanical:
#   * escape as `??|` in the changesets, or
#   * rewrite to the function form, jsonb_exists_any(options, array[...]).
# Until then stack-up.sh uses its own applied-once loop, which works.
# Apply the Liquibase changelog (ADR-020).
#
# Liquibase rather than re-running .sql files: each changeset is applied once, recorded in
# DATABASECHANGELOG with a checksum, so editing an applied changeset fails loudly instead
# of diverging silently from what the database actually contains.
#
# Changesets create SCHEMA ONLY. No rows: a fresh database is genuinely empty and every
# row arrives through Administration -> Initial Data.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_CONTAINER="${AKG_PG_CONTAINER:-akg-postgres}"
PG_PORT="${AKG_PG_PORT:-5432}"
NETWORK="${AKG_NETWORK:-akg-net}"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null
docker network connect "$NETWORK" "$PG_CONTAINER" >/dev/null 2>&1 || true

docker run --rm \
  --network "$NETWORK" \
  -v "$HERE/Postgres/liquibase:/liquibase/changelog" \
  liquibase/liquibase:4.29 \
  --search-path=/liquibase/changelog \
  --changelog-file=changelog-master.yaml \
  --url="jdbc:postgresql://${PG_CONTAINER}:5432/akg" \
  --username=akg \
  --password="${AKG_PG_PASSWORD:-akg-local-only}" \
  --log-level=warning \
  update
