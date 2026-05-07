#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8000}"
: "${RUN_MIGRATIONS:=true}"
: "${RUN_COLLECTSTATIC:=true}"
: "${MIGRATE_RETRIES:=15}"
: "${MIGRATE_RETRY_SLEEP_SECONDS:=2}"
: "${GUNICORN_TIMEOUT:=30}"
: "${INSTALL_PLAYWRIGHT_BROWSERS:=false}"

# Optional: ensure Playwright Chromium exists at runtime.
# In platforms like Render, the build step might not run `./build.sh` (or caches may be ephemeral).
# When enabled, we install browsers at boot if needed (idempotent).
_pw_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${_pw_flag}" = "true" ] || [ "${_pw_flag}" = "1" ] || [ "${_pw_flag}" = "yes" ] || [ "${_pw_flag}" = "on" ]; then
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"
  python -m playwright install chromium || true
fi

# Media root (uploads). In Render the repo path can be read-only at runtime; default to /tmp.
MEDIA_ROOT_DIR="${MEDIA_ROOT:-media}"
mkdir -p "${MEDIA_ROOT_DIR}" || true

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

exec gunicorn webstats.wsgi:application --bind "0.0.0.0:${PORT}" --timeout "${GUNICORN_TIMEOUT}"
