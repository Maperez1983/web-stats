#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8000}"
: "${RUN_MIGRATIONS:=true}"
: "${MIGRATE_RETRIES:=15}"
: "${MIGRATE_RETRY_SLEEP_SECONDS:=2}"
: "${GUNICORN_TIMEOUT:=120}"
: "${GUNICORN_WORKERS:=2}"
: "${GUNICORN_THREADS:=2}"
: "${GUNICORN_KEEPALIVE:=5}"
: "${GUNICORN_GRACEFUL_TIMEOUT:=30}"
: "${INSTALL_PLAYWRIGHT_BROWSERS:=false}"
: "${INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME:=false}"

# En Render, `collectstatic` suele ejecutarse en build. Si no has definido explícitamente
# RUN_COLLECTSTATIC, lo desactivamos al detectar Render para acelerar el bind del puerto.
if [ -z "${RUN_COLLECTSTATIC+x}" ]; then
  if [ -n "${RENDER:-}" ] || [ -n "${RENDER_SERVICE_ID:-}" ] || [ -n "${RENDER_GIT_COMMIT:-}" ]; then
    RUN_COLLECTSTATIC="false"
  else
    RUN_COLLECTSTATIC="true"
  fi
fi

# Playwright: instala Chromium en build (`build.sh`) con `INSTALL_PLAYWRIGHT_BROWSERS=true`.
# Runtime NO instala nada por defecto (evita arranques lentos / "No open ports detected").
_pw_build_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_pw_rt_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_pw_rt_install="false"
if [ "${_pw_rt_flag}" = "true" ] || [ "${_pw_rt_flag}" = "1" ] || [ "${_pw_rt_flag}" = "yes" ] || [ "${_pw_rt_flag}" = "on" ]; then
  _pw_rt_install="true"
elif [ "${_pw_build_flag}" = "true" ] || [ "${_pw_build_flag}" = "1" ] || [ "${_pw_build_flag}" = "yes" ] || [ "${_pw_build_flag}" = "on" ]; then
  echo "[boot] Aviso: INSTALL_PLAYWRIGHT_BROWSERS está pensado para el build. Runtime no instalará Chromium; usa INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME=true (no recomendado) si lo necesitas." >&2
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

gunicorn webstats.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
  --keep-alive "${GUNICORN_KEEPALIVE}" \
  --workers "${GUNICORN_WORKERS}" \
  --threads "${GUNICORN_THREADS}" \
  --access-logfile - \
  --error-logfile - &
server_pid="$!"

# Si alguien insiste en instalar Chromium en runtime, lo hacemos DESPUÉS de abrir el puerto.
if [ "${_pw_rt_install}" = "true" ]; then
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"
  python -m playwright install chromium || true
fi

trap 'kill -TERM "${server_pid}" 2>/dev/null || true' TERM INT
wait "${server_pid}"
