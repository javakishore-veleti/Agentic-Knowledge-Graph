#!/usr/bin/env bash
# Start every API service DETACHED, each on its own port.
#
# Run directly, not through a pipe: a detached uvicorn keeps the inherited pipe open, so
# `mw-start-all.sh | tail` appears to hang even though the services are up.
. "$(dirname "${BASH_SOURCE[0]}")/_services.sh"

# Schema first: a schema change ships with the code change that needs it, so starting the
# services is the natural moment to apply it rather than a separate step to remember.
echo "==> schema"
"$REPO_ROOT/CICD/Local/db-apply-migrations.sh"


for svc in $SERVICES; do
  port="$(port_of "$svc")"

  if pid="$(svc_pid "$svc")"; then
    echo "==  $svc already running (pid $pid, port $port)"
    continue
  fi
  if port_busy "$port"; then
    holder="$(listener_pid "$port")"
    echo "!!  port $port is held by another process (pid $holder); skipping $svc" >&2
    ps -o command= -p "$holder" 2>/dev/null | cut -c1-80 | sed 's/^/      /' >&2
    continue
  fi

  log="$(log_file "$svc")"
  # </dev/null so the child does not inherit the caller's stdin and hold it open.
  ( cd "$(path_of "$svc")" \
    && AKG_DATABASE_URL="$(db_url)" exec nohup uv run \
         --with 'fastapi>=0.115' --with 'uvicorn[standard]>=0.32' \
         --with 'pydantic-settings>=2.6' --with 'httpx>=0.27' \
         $(deps_of "$svc") --python 3.13 \
         --with-editable ../../Libraries/python/akg-service-core --with-editable . \
         uvicorn "$(module_of "$svc")" --host 0.0.0.0 --port "$port" \
         < /dev/null > "$log" 2>&1 ) &
  disown 2>/dev/null || true
  echo "==> $svc starting -> ${log#"$REPO_ROOT/"}"
done

echo ""
echo "waiting up to 60s each for a first response (first run installs dependencies)..."
for svc in $SERVICES; do
  port="$(port_of "$svc")"
  ok=no; i=0
  while [ "$i" -lt 60 ]; do
    if curl -fsS -o /dev/null "http://localhost:$port/health" 2>/dev/null; then ok=yes; break; fi
    i=$((i + 1)); sleep 1
  done
  if [ "$ok" = yes ]; then
    echo "  $svc  ready    pid $(svc_pid "$svc")    http://localhost:$port"
  else
    # Never report ready after a timeout: that is how a broken start looks like a working
    # one, which cost an afternoon once already.
    echo "  $svc  NOT READY — last log lines:" >&2
    tail -6 "$(log_file "$svc")" 2>/dev/null | sed 's/^/      /' >&2
  fi
done
