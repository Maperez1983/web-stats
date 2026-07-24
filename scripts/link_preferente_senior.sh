#!/usr/bin/env bash
#
# Vincula los equipos SENIOR a su ficha de La Preferente, desde tu máquina (IP residencial).
#
# ¿Por qué desde tu máquina y no en Render?
#   La Preferente (Cloudflare) devuelve 403 desde la IP del datacenter de Render. La detección de
#   la URL del equipo (find_preferente_team_url) SOLO funciona desde una conexión doméstica.
#   Universo RFAF sí funciona en el servidor: eso se resuelve solo con el botón del onboarding o
#   con `autolink_competition_contexts` en Render. Este script cubre únicamente el hueco de senior.
#
# Qué hace:
#   1) SIMULACIÓN (sin escribir): muestra qué senior se vincularían y a qué URL.
#   2) Si confirmas (APPLY=1), aplica --commit --sync escribiendo en la BD que le indiques.
#
# Uso (contra la BD de PRODUCCIÓN, desde tu equipo):
#   export DATABASE_URL='postgres://USER:PASS@HOST:PORT/DBNAME'   # la de producción
#   ./scripts/link_preferente_senior.sh            # simulación (no escribe nada)
#   APPLY=1 ./scripts/link_preferente_senior.sh    # aplica de verdad
#
# Opcional:
#   WORKSPACE=mi-club ./scripts/link_preferente_senior.sh   # limita a un club (slug)
#
# Requisitos: entorno del proyecto (mismas deps que el server) y acceso de red a esa BD.
#
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: define DATABASE_URL con la base de datos destino (producción)." >&2
  echo "  export DATABASE_URL='postgres://USER:PASS@HOST:PORT/DBNAME'" >&2
  exit 1
fi

PY="${PYTHON:-python3}"
WS_ARG=()
if [[ -n "${WORKSPACE:-}" ]]; then
  WS_ARG=(--workspace "${WORKSPACE}")
fi

echo "== Base de datos: ${DATABASE_URL%%@*}@… (destino) =="
echo "== Paso 1/2: SIMULACIÓN (no se escribe nada) =="
"$PY" manage.py autolink_competition_contexts --only-preferente --senior-only "${WS_ARG[@]}"

if [[ "${APPLY:-0}" != "1" ]]; then
  echo
  echo "Simulación terminada. Para APLICAR de verdad:"
  echo "  APPLY=1 ${0}"
  exit 0
fi

echo
echo "== Paso 2/2: APLICANDO (--commit --sync) =="
"$PY" manage.py autolink_competition_contexts --only-preferente --senior-only --commit --sync "${WS_ARG[@]}"
echo
echo "Hecho. Las URLs de La Preferente quedan guardadas en Team.preferente_url (persisten)."
echo "Nota: la clasificación de Preferente se sirve desde snapshots cacheados; el servidor no la trae en vivo."
