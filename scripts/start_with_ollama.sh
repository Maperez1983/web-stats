#!/usr/bin/env bash
set -euo pipefail

: "${ENABLE_OLLAMA:=false}"
: "${OLLAMA_MODEL:=${AI_TRAINER_LOCAL_LLM_MODEL:-qwen3:1.7b}}"
: "${AI_TRAINER_LOCAL_LLM_MODEL:=${OLLAMA_MODEL}}"
: "${AI_TRAINER_OLLAMA_URL:=http://127.0.0.1:11434}"

export AI_TRAINER_LOCAL_LLM_MODEL
export AI_TRAINER_OLLAMA_URL

_flag="$(echo "${ENABLE_OLLAMA:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
ollama_pid=""

_cleanup() {
  if [ -n "${ollama_pid}" ]; then
    kill -TERM "${ollama_pid}" 2>/dev/null || true
  fi
}
trap _cleanup EXIT TERM INT

_wait_for_ollama() {
  python - <<'PY'
import os
import time
import urllib.request

base_url = os.environ.get("AI_TRAINER_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
deadline = time.time() + int(os.environ.get("OLLAMA_BOOT_TIMEOUT", "30"))
while time.time() < deadline:
    try:
        with urllib.request.urlopen(base_url + "/api/tags", timeout=2) as response:
            if 200 <= response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)
PY
}

if [ "${_flag}" = "true" ] || [ "${_flag}" = "1" ] || [ "${_flag}" = "yes" ] || [ "${_flag}" = "on" ]; then
  if command -v ollama >/dev/null 2>&1; then
    echo "[boot] Starting Ollama local LLM: ${OLLAMA_MODEL}" >&2
    ollama serve &
    ollama_pid="$!"
    (
      if _wait_for_ollama; then
        ollama pull "${OLLAMA_MODEL}" || true
      else
        echo "[boot] Ollama did not become ready before timeout; Django will start anyway." >&2
      fi
    ) &
  else
    echo "[boot] ENABLE_OLLAMA=${ENABLE_OLLAMA}, but the ollama binary is not installed. Django will start without local LLM." >&2
  fi
fi

# Fotos HD de las pizarras de tarea, si nadie más las está haciendo.
#
# POR QUÉ TAMBIÉN AQUÍ (2026-08-08). El sitio bueno es el worker, que no atiende peticiones. Pero
# el 8 de agosto el log de ese servicio no mostraba NINGUNA línea de su propio script —ni las mías
# ni las tres que ya existían— aunque el Start Command era el correcto, así que no hubo forma de
# confirmar que sus bucles corrieran. Este servicio sí ejecuta su script: se ve porque arranca
# Ollama. Con el encargo guardado en la base, que fotografíe uno u otro da igual, y que lo hagan
# los dos también: `claim_pending` usa `select_for_update(skip_locked=True)` y un alquiler, así
# que dos procesos nunca cogen el mismo encargo.
#
# Va DESPACIO a propósito: una foto por pasada y descanso largo. Aquí Chromium comparte máquina
# con los workers de gunicorn que tienen que servirle la página del editor, y no queremos que la
# app se resienta por ponerse al día más rápido.
#
# Se enciende SOLO si BOARD_SHOT_BASE_URL está puesta. Sin ella no arranca y lo dice.
if [ -n "${BOARD_SHOT_BASE_URL:-}" ]; then
  (
    sleep "${BOARD_SHOT_BOOT_DELAY_SECONDS:-180}"
    while true; do
      python manage.py fotos_pizarra --max "${BOARD_SHOT_BATCH:-1}" \
        || echo "[fotos-pizarra] la pasada falló; se reintentará" >&2
      sleep "${BOARD_SHOT_INTERVAL_SECONDS:-180}"
    done
  ) &
  echo "[fotos-pizarra] cola activada contra ${BOARD_SHOT_BASE_URL} (1 foto cada ${BOARD_SHOT_INTERVAL_SECONDS:-180}s)" >&2
else
  echo "[fotos-pizarra] no activada aquí (sin BOARD_SHOT_BASE_URL)" >&2
fi

exec ./start_asgi.sh
