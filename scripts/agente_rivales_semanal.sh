#!/usr/bin/env bash
# Envoltorio para la ejecucion programada del agente de plantillas rivales.
#
# Lee la configuracion de ~/.sj_agente.env (que NO va al repositorio) para que el
# token no acabe en el historial del terminal ni en git. Deja un registro en
# ~/Library/Logs/sj_agente_rivales.log para poder revisar que paso.
set -uo pipefail

CONFIG="${HOME}/.sj_agente.env"
LOG="${HOME}/Library/Logs/sj_agente_rivales.log"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$(dirname "$LOG")"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

if [ ! -f "$CONFIG" ]; then
  echo "Falta $CONFIG. Crealo con SJ_INGEST_TOKEN, SJ_COMPETICION_URL y SJ_BASE_URL." >> "$LOG"
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$CONFIG"; set +a

cd "$REPO" || exit 1

# Trae la ultima version del agente antes de correr, para que no se quede atras.
git fetch -q --depth 1 origin main >> "$LOG" 2>&1 && git reset --hard -q origin/main >> "$LOG" 2>&1 || \
  echo "aviso: no se pudo actualizar el codigo; sigo con la version local" >> "$LOG"

python3 scripts/agente_rivales.py >> "$LOG" 2>&1
codigo=$?
echo "salida: $codigo" >> "$LOG"
exit $codigo
