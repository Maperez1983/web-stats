#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8000}"
: "${RUN_MIGRATIONS:=true}"
: "${MIGRATE_RETRIES:=15}"
: "${MIGRATE_RETRY_SLEEP_SECONDS:=2}"
: "${MIGRATE_FAIL_OPEN:=}"
: "${GUNICORN_TIMEOUT:=120}"
: "${GUNICORN_WORKERS:=2}"
: "${GUNICORN_THREADS:=4}"
: "${GUNICORN_KEEPALIVE:=5}"
: "${GUNICORN_GRACEFUL_TIMEOUT:=30}"
: "${INSTALL_PLAYWRIGHT_BROWSERS:=false}"
: "${INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME:=false}"
: "${DJANGO_RUN_ASGI:=false}"

# En Render, `collectstatic` ya se ejecuta en build (`build.sh`). Repetirlo en runtime solo retrasa
# el bind al puerto y puede provocar "No open ports detected".
# Si no has definido explícitamente RUN_COLLECTSTATIC, lo desactivamos al detectar Render.
if [ -z "${RUN_COLLECTSTATIC+x}" ]; then
  if [ -n "${RENDER:-}" ] || [ -n "${RENDER_SERVICE_ID:-}" ] || [ -n "${RENDER_GIT_COMMIT:-}" ]; then
    RUN_COLLECTSTATIC="false"
  else
    RUN_COLLECTSTATIC="true"
  fi
fi

# Playwright (chromium/firefox/webkit) es pesado (descarga bastante) y en Render puede hacer que el deploy falle
# por "No open ports detected" si se ejecuta ANTES del bind del puerto.
# Recomendación: instala navegadores en build (`build.sh`) con `INSTALL_PLAYWRIGHT_BROWSERS=true` y
# `PLAYWRIGHT_BROWSERS_PATH=0`. En runtime NO instalamos nada por defecto.
_pw_build_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_pw_rt_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
_pw_rt_install="false"
if [ "${_pw_rt_flag}" = "true" ] || [ "${_pw_rt_flag}" = "1" ] || [ "${_pw_rt_flag}" = "yes" ] || [ "${_pw_rt_flag}" = "on" ]; then
  _pw_rt_install="true"
elif [ "${_pw_build_flag}" = "true" ] || [ "${_pw_build_flag}" = "1" ] || [ "${_pw_build_flag}" = "yes" ] || [ "${_pw_build_flag}" = "on" ]; then
  echo "[boot] Aviso: INSTALL_PLAYWRIGHT_BROWSERS está pensado para el build. Runtime no instalará navegadores; usa INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME=true (no recomendado) si lo necesitas." >&2
fi

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  _migrate_fail_open="$(echo "${MIGRATE_FAIL_OPEN:-}" | tr '[:upper:]' '[:lower:]' | xargs)"
  if [ -z "${_migrate_fail_open}" ]; then
    # En Render priorizamos disponibilidad: si el DB está en mantenimiento o hay un lock temporal,
    # preferimos arrancar el servidor y mostrar UI parcial antes que devolver 502 por no poder migrar.
    if [ -n "${RENDER:-}" ] || [ -n "${RENDER_SERVICE_ID:-}" ] || [ -n "${RENDER_GIT_COMMIT:-}" ]; then
      _migrate_fail_open="true"
    else
      _migrate_fail_open="false"
    fi
  fi
  attempt=1
  while true; do
    if python manage.py migrate --noinput; then
      break
    fi
    if [ "${attempt}" -ge "${MIGRATE_RETRIES}" ]; then
      if [ "${_migrate_fail_open}" = "true" ] || [ "${_migrate_fail_open}" = "1" ] || [ "${_migrate_fail_open}" = "yes" ] || [ "${_migrate_fail_open}" = "on" ]; then
        echo "[boot] manage.py migrate failed after ${MIGRATE_RETRIES} attempts; continuing anyway (MIGRATE_FAIL_OPEN=${_migrate_fail_open})." >&2
        break
      fi
      echo "[boot] manage.py migrate failed after ${MIGRATE_RETRIES} attempts" >&2
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
_start_server() {
  _threads="${GUNICORN_THREADS:-1}"
  if [ -z "${_threads}" ]; then _threads="1"; fi
  if ! [[ "${_threads}" =~ ^[0-9]+$ ]]; then _threads="1"; fi
  if [ "${_threads}" -lt 1 ]; then _threads="1"; fi

  if [ "${_run_asgi}" = "true" ]; then
    echo "[boot] DJANGO_RUN_ASGI=${DJANGO_RUN_ASGI:-} -> starting ASGI (UvicornWorker)" >&2
    gunicorn webstats.asgi:application \
      -k uvicorn.workers.UvicornWorker \
      --bind "0.0.0.0:${PORT}" \
      --timeout "${GUNICORN_TIMEOUT}" \
      --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
      --keep-alive "${GUNICORN_KEEPALIVE}" \
      --workers "${GUNICORN_WORKERS}" \
      --access-logfile - \
      --error-logfile - &
  else
    if [ "${_threads}" -gt 1 ]; then
      echo "[boot] DJANGO_RUN_ASGI=${DJANGO_RUN_ASGI:-} -> starting WSGI (gthread ${GUNICORN_WORKERS}x${_threads})" >&2
      gunicorn webstats.wsgi:application \
        -k gthread \
        --threads "${_threads}" \
        --bind "0.0.0.0:${PORT}" \
        --timeout "${GUNICORN_TIMEOUT}" \
        --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
        --keep-alive "${GUNICORN_KEEPALIVE}" \
        --workers "${GUNICORN_WORKERS}" \
        --access-logfile - \
        --error-logfile - &
    else
      echo "[boot] DJANGO_RUN_ASGI=${DJANGO_RUN_ASGI:-} -> starting WSGI (sync ${GUNICORN_WORKERS})" >&2
    gunicorn webstats.wsgi:application \
      -k sync \
      --bind "0.0.0.0:${PORT}" \
      --timeout "${GUNICORN_TIMEOUT}" \
      --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
      --keep-alive "${GUNICORN_KEEPALIVE}" \
      --workers "${GUNICORN_WORKERS}" \
      --access-logfile - \
      --error-logfile - &
    fi
  fi
  echo $!
}

server_pid="$(_start_server)"

# Si alguien insiste en instalar Chromium en runtime, lo hacemos DESPUÉS de abrir el puerto
# para no romper el deploy en Render.
if [ "${_pw_rt_install}" = "true" ]; then
  if [ -n "${RENDER:-}" ] || [ -n "${RENDER_SERVICE_ID:-}" ] || [ -n "${RENDER_GIT_COMMIT:-}" ]; then
    echo "[boot] Aviso: INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME está activado en Render; puede ralentizar y consumir disco." >&2
  fi
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"
  python -m playwright install chromium firefox webkit || true
fi

trap 'kill -TERM "${server_pid}" 2>/dev/null || true' TERM INT
wait "${server_pid}"
