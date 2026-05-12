#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8000}"
: "${RUN_MIGRATIONS:=true}"
: "${RUN_COLLECTSTATIC:=false}"
: "${MIGRATE_RETRIES:=15}"
: "${MIGRATE_RETRY_SLEEP_SECONDS:=2}"
: "${GUNICORN_TIMEOUT:=30}"
: "${INSTALL_PLAYWRIGHT_BROWSERS:=false}"
: "${DJANGO_RUN_ASGI:=false}"

# Ensure Playwright Chromium exists at runtime (idempotent).
# Render instances are ephemeral; even if Chromium was installed manually in a previous shell,
# a restart/deploy can land on a fresh instance where `.local-browsers/` doesn't exist.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"
_pw_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_should_install_pw="false"
if [ "${_pw_flag}" = "true" ] || [ "${_pw_flag}" = "1" ] || [ "${_pw_flag}" = "yes" ] || [ "${_pw_flag}" = "on" ]; then
  _should_install_pw="true"
else
  # Auto-repair: if Playwright is installed but Chromium isn't present, download it.
  python - <<'PY' >/dev/null 2>&1 || _should_install_pw="true"
import os
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.getenv("PLAYWRIGHT_BROWSERS_PATH", "0"))
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch(args=["--no-sandbox"])
b.close()
p.stop()
PY
fi
if [ "${_should_install_pw}" = "true" ]; then
  python -m playwright install chromium || true
fi

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  attempt=1
  while true; do
    if python manage.py migrate --noinput; then
      break
    fi
    if [ "${attempt}" -ge "${MIGRATE_RETRIES}" ]; then
      echo "manage.py migrate failed after ${MIGRATE_RETRIES} attempts" >&2
      exit 1
    fi
    echo "manage.py migrate failed (attempt ${attempt}/${MIGRATE_RETRIES}); retrying in ${MIGRATE_RETRY_SLEEP_SECONDS}s..." >&2
    attempt=$((attempt + 1))
    sleep "${MIGRATE_RETRY_SLEEP_SECONDS}"
  done
fi

if [ "${RUN_COLLECTSTATIC}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

_run_asgi_flag="$(echo "${DJANGO_RUN_ASGI:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_run_asgi="false"
if [ "${_run_asgi_flag}" = "true" ] || [ "${_run_asgi_flag}" = "1" ] || [ "${_run_asgi_flag}" = "yes" ] || [ "${_run_asgi_flag}" = "on" ]; then
  _run_asgi="true"
fi

# Default: WSGI.
# Motivo: gran parte del stack es sync y, bajo ASGI, cualquier fuga de sync en un hilo con event-loop
# puede provocar `SynchronousOnlyOperation` (p.ej. al guardar sesiones).
if [ "${_run_asgi}" = "true" ]; then
  echo "[boot] DJANGO_RUN_ASGI=${DJANGO_RUN_ASGI:-} -> starting ASGI (UvicornWorker)" >&2
  exec gunicorn webstats.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${PORT}" \
    --timeout "${GUNICORN_TIMEOUT}"
fi

echo "[boot] DJANGO_RUN_ASGI=${DJANGO_RUN_ASGI:-} -> starting WSGI" >&2
exec gunicorn webstats.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --timeout "${GUNICORN_TIMEOUT}"
