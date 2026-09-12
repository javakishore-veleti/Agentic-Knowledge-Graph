#!/usr/bin/env bash
# DataCatalog tests against a throwaway Postgres.
#
# Deliberately not mocked: what is worth testing here is the database's own constraints
# and views (one CDC instance per MIO, no credentials in endpoint options, a live MIO must
# name its pin). A mock would only assert that the mock works.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
NAME=akg-catalog-test
PORT=55432

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker info >/dev/null 2>&1 || { echo "docker daemon not running" >&2; exit 1; }
cleanup
docker run -d --name "$NAME" -p "$PORT:5432" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=akg -e POSTGRES_USER=akg \
  pgvector/pgvector:pg16 >/dev/null

printf "waiting for postgres"
i=0
while [ "$i" -lt 60 ]; do
  if docker exec "$NAME" pg_isready -U akg -d akg >/dev/null 2>&1; then break; fi
  printf "."; i=$((i + 1)); sleep 1
done
echo " ready"

for f in "$HERE"/Postgres/init/*.sql; do
  docker exec -i "$NAME" psql -U akg -d akg -q -v ON_ERROR_STOP=1 < "$f" >/dev/null
  echo "  applied $(basename "$f")"
done

export AKG_DATABASE_URL="postgresql+psycopg://akg:test@localhost:$PORT/akg"
cd "$REPO_ROOT/Middleware/data-catalog"
uv run --with 'fastapi>=0.115' --with 'sqlalchemy>=2.0' --with 'psycopg[binary]>=3.2' \
       --with 'pydantic-settings>=2.6' --with pytest --with httpx --python 3.13 \
       --with-editable . python -m pytest tests -q -p no:warnings
