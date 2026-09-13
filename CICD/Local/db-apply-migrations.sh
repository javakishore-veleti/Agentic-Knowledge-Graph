#!/usr/bin/env bash
# Apply any migration that has not run yet. Assumes Postgres is already up.
#
# Each file is applied exactly once and recorded in catalog.schema_migrations. Re-applying
# the whole set on every start quietly requires every migration to stay compatible with
# every later one -- 010 inserts rows, 011 later adds a NOT NULL column to that table, and
# re-running 010 then fails. Replaying history is the mistake, not either migration.
#
# Called by middleware start, so a schema change ships with the code change that needs it.
# In a deployed environment this belongs in its own job rather than in service startup:
# several replicas starting together would race, and one of them would lose.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_CONTAINER="${AKG_PG_CONTAINER:-akg-postgres}"
QUIET="${1:-}"

say() { [ "$QUIET" = "--quiet" ] || echo "$@"; }

if ! docker exec "$PG_CONTAINER" pg_isready -U akg -d akg >/dev/null 2>&1; then
  echo "!!  $PG_CONTAINER is not accepting connections." >&2
  echo "    run: npm run local:containers:start-all" >&2
  exit 1
fi

docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q -v ON_ERROR_STOP=1 \
  < "$HERE/Postgres/init/000-migrations.sql" >/dev/null

applied=0; skipped=0
for f in "$HERE"/Postgres/init/*.sql; do
  name="$(basename "$f")"
  [ "$name" = "000-migrations.sql" ] && continue
  seen="$(docker exec -i "$PG_CONTAINER" psql -U akg -d akg -tAq \
    -c "SELECT 1 FROM catalog.schema_migrations WHERE filename = '$name'" 2>/dev/null || true)"
  if [ "$seen" = "1" ]; then skipped=$((skipped + 1)); continue; fi
  if ! docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q -v ON_ERROR_STOP=1 < "$f" >/dev/null 2>&1; then
    echo "!!  $name failed:" >&2
    docker exec -i "$PG_CONTAINER" psql -U akg -d akg -v ON_ERROR_STOP=1 < "$f" 2>&1 \
      | grep -i "^ERROR" | head -3 | sed 's/^/      /' >&2
    exit 1
  fi
  docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q \
    -c "INSERT INTO catalog.schema_migrations (filename) VALUES ('$name') ON CONFLICT DO NOTHING" >/dev/null
  applied=$((applied + 1))
  say "    applied $name"
done

if [ "$applied" -gt 0 ]; then
  say "    $applied new migration(s), $skipped already present"
else
  say "    schema up to date ($skipped migrations)"
fi
