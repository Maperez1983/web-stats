#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8000}"
: "${RUN_MIGRATIONS:=true}"
: "${RUN_COLLECTSTATIC:=true}"
: "${MIGRATE_RETRIES:=15}"
: "${MIGRATE_RETRY_SLEEP_SECONDS:=2}"

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

exec gunicorn webstats.wsgi:application --bind "0.0.0.0:${PORT}"
