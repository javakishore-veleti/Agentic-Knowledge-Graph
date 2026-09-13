#!/usr/bin/env bash
# Bring up everything needed to use the portal against real data:
# Postgres, the migrations, and the DataCatalog API.
#
# On a blank database every list is empty until Administration -> Initial Data has been
# run. That is the intended first-run experience, not a failure.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
RUN_DIR="$REPO_ROOT/.local-run"
mkdir -p "$RUN_DIR"

PG_CONTAINER="${AKG_PG_CONTAINER:-akg-postgres}"
PG_PORT="${AKG_PG_PORT:-5432}"
API_PORT="${AKG_CATALOG_PORT:-9001}"

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "docker daemon not running" >&2; exit 1; }

echo "==> Postgres"
# Delegated to the compose tier rather than started here with `docker run`.
#
# Both existed before, creating the same container name two different ways: a plain
# `docker run` container carries no compose labels, so `containers:stop-all` found nothing
# to stop and said so in a warning while Postgres kept running. One owner per container.
"$HERE/docker-all-up.sh" Postgres >/dev/null

printf "    waiting"
i=0
until docker exec "$PG_CONTAINER" pg_isready -U akg -d akg >/dev/null 2>&1; do
  [ "$i" -ge 60 ] && { echo " TIMEOUT" >&2; docker logs --tail 15 "$PG_CONTAINER" >&2; exit 1; }
  printf "."; i=$((i + 1)); sleep 1
done
echo " ready"

echo "==> migrations"
# Applied exactly once each, tracked in catalog.schema_migrations (ADR-020). Re-running
# the whole set every start forces every migration to stay compatible with every later
# one, which stops being true the moment one adds a NOT NULL column to a table an earlier
# one inserts into.
docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q -v ON_ERROR_STOP=1 \
  < "$HERE/Postgres/init/000-migrations.sql" >/dev/null

applied=0
skipped=0
for f in "$HERE"/Postgres/init/*.sql; do
  name="$(basename "$f")"
  [ "$name" = "000-migrations.sql" ] && continue
  already="$(docker exec -i "$PG_CONTAINER" psql -U akg -d akg -tAq \
    -c "SELECT 1 FROM catalog.schema_migrations WHERE filename = '$name'" 2>/dev/null || true)"
  if [ "$already" = "1" ]; then
    skipped=$((skipped + 1))
    continue
  fi
  if ! docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q -v ON_ERROR_STOP=1 < "$f" >/dev/null; then
    echo "!!  $name failed; the database is left as the migration found it" >&2
    docker exec -i "$PG_CONTAINER" psql -U akg -d akg -v ON_ERROR_STOP=1 < "$f" 2>&1 \
      | grep -i "^ERROR" | head -3 | sed 's/^/      /' >&2
    exit 1
  fi
  docker exec -i "$PG_CONTAINER" psql -U akg -d akg -q \
    -c "INSERT INTO catalog.schema_migrations (filename) VALUES ('$name') ON CONFLICT DO NOTHING" >/dev/null
  applied=$((applied + 1))
  echo "    applied $name"
done
echo "    $applied applied, $skipped already present"

echo "==> DataCatalog API on :${API_PORT}"
if curl -fsS -o /dev/null "http://localhost:${API_PORT}/health" 2>/dev/null; then
  echo "    already running"
else
  # Something else holding the port makes uvicorn exit with "address already in use",
  # which is easy to miss in a log. Docker Desktop holds 8001 on macOS, which is how this
  # check earned its place.
  holder="$( { lsof -ti tcp:"$API_PORT" -sTCP:LISTEN 2>/dev/null || true; } | head -1)"
  if [ -n "$holder" ]; then
    echo "!!  port $API_PORT is held by another process:" >&2
    ps -o command= -p "$holder" 2>/dev/null | cut -c1-90 | sed 's/^/      /' >&2
    echo "    set AKG_CATALOG_PORT to a free port and re-run." >&2
    exit 1
  fi
  log="$RUN_DIR/data-catalog.log"
  ( cd "$REPO_ROOT/Middleware/data-catalog" \
    && AKG_DATABASE_URL="postgresql+psycopg://akg:akg-local-only@localhost:${PG_PORT}/akg" \
       nohup uv run --with 'fastapi>=0.115' --with 'uvicorn[standard]>=0.32' \
         --with 'sqlalchemy>=2.0' --with 'psycopg[binary]>=3.2' \
         --with 'pydantic-settings>=2.6' --python 3.13 \
         --with-editable ../../Libraries/python/akg-service-core --with-editable . \
         uvicorn data_catalog.app:app --host 0.0.0.0 --port "$API_PORT" \
         < /dev/null > "$log" 2>&1 & ) 
  printf "    starting"
  i=0
  ok=no
  while [ "$i" -lt 60 ]; do
    if curl -fsS -o /dev/null "http://localhost:${API_PORT}/health" 2>/dev/null; then
      ok=yes; break
    fi
    printf "."; i=$((i + 1)); sleep 1
  done
  if [ "$ok" != yes ]; then
    # Reporting "ready" after a timeout is how a broken start looks like a working one.
    echo " FAILED" >&2
    echo "    the API did not answer on :${API_PORT}. Last lines of the log:" >&2
    tail -12 "$log" | sed 's/^/      /' >&2
    exit 1
  fi
  echo " ready -> ${log#"$REPO_ROOT/"}"
fi

echo ""
curl -s "http://localhost:${API_PORT}/health" || true
echo ""
echo ""
echo "Next:"
echo "  npm run local:ui:start-all          Admin on :9003, Customer on :9004"
echo "  open http://localhost:9003/administration/initial-data   load the reference data"
