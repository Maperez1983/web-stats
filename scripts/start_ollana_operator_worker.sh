#!/usr/bin/env bash
set -euo pipefail

: "${OLLANA_OPERATOR_ENABLED:=false}"
: "${OLLANA_OPERATOR_WORKSPACE_ID:=}"
: "${OLLANA_OPERATOR_ACTOR_ID:=0}"
: "${OLLANA_OPERATOR_SLEEP_SECONDS:=30}"
: "${OLLANA_OPERATOR_MAX_RUNTIME_SECONDS:=0}"
: "${OLLANA_OPERATOR_FORCE:=true}"
: "${ENABLE_OLLAMA:=false}"
: "${OLLAMA_MODEL:=${AI_TRAINER_LOCAL_LLM_MODEL:-qwen3:1.7b}}"
: "${AI_TRAINER_LOCAL_LLM_MODEL:=${OLLAMA_MODEL}}"
: "${AI_TRAINER_OLLAMA_URL:=http://127.0.0.1:11434}"

export AI_TRAINER_LOCAL_LLM_MODEL
export AI_TRAINER_OLLAMA_URL

flag="$(echo "${OLLANA_OPERATOR_ENABLED:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${flag}" != "true" ] && [ "${flag}" != "1" ] && [ "${flag}" != "yes" ] && [ "${flag}" != "on" ]; then
  echo "[ollana-operator] OLLANA_OPERATOR_ENABLED=${OLLANA_OPERATOR_ENABLED}. Worker desactivado." >&2
  exit 0
fi

if [ -z "${OLLANA_OPERATOR_WORKSPACE_ID}" ]; then
  echo "[ollana-operator] Falta OLLANA_OPERATOR_WORKSPACE_ID." >&2
  exit 1
fi

ollama_pid=""

cleanup() {
  if [ -n "${ollama_pid}" ]; then
    kill -TERM "${ollama_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT TERM INT

wait_for_ollama() {
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

llm_flag="$(echo "${ENABLE_OLLAMA:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${llm_flag}" = "true" ] || [ "${llm_flag}" = "1" ] || [ "${llm_flag}" = "yes" ] || [ "${llm_flag}" = "on" ]; then
  if command -v ollama >/dev/null 2>&1; then
    echo "[ollana-operator] Starting Ollama local LLM: ${OLLAMA_MODEL}" >&2
    ollama serve &
    ollama_pid="$!"
    (
      if wait_for_ollama; then
        ollama pull "${OLLAMA_MODEL}" || true
      else
        echo "[ollana-operator] Ollama no estuvo listo a tiempo; el operador seguirá sin bloquearse." >&2
      fi
    ) &
  else
    echo "[ollana-operator] ENABLE_OLLAMA activo pero no existe el binario ollama." >&2
  fi
fi

force_args=()
force_flag="$(echo "${OLLANA_OPERATOR_FORCE:-true}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${force_flag}" = "true" ] || [ "${force_flag}" = "1" ] || [ "${force_flag}" = "yes" ] || [ "${force_flag}" = "on" ]; then
  force_args+=(--force)
fi

# --- Autogeneración de avatares en 2º plano (reusa este worker; sin servicio/cron nuevo) ---
# Corre generate_player_avatars cada AVATAR_AUTOGEN_INTERVAL_SECONDS. Es INCREMENTAL: si no
# cambió nada, sale enseguida y consume poco. Guardado con salvaguardas para no tumbar al operador:
#   - solo si AVATAR_AUTOGEN_ENABLED=true y el modelo está presente,
#   - toda la generación va con `|| true` (un fallo/OOM del batch no mata el operador),
#   - primera pasada tras 120s (deja arrancar al operador antes).
avatar_flag="$(echo "${AVATAR_AUTOGEN_ENABLED:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
avatar_model="${AVATAR_INSWAPPER:-/opt/render/project/src/vendor/inswapper_128.onnx}"
if { [ "${avatar_flag}" = "true" ] || [ "${avatar_flag}" = "1" ] || [ "${avatar_flag}" = "yes" ]; } && [ -f "${avatar_model}" ]; then
  (
    sleep 120
    while true; do
      echo "[avatars] pasada de generación ($(date -u))" >&2
      python manage.py generate_player_avatars --all || echo "[avatars] la pasada falló; sigo" >&2
      sleep "${AVATAR_AUTOGEN_INTERVAL_SECONDS:-86400}"
    done
  ) &
  echo "[avatars] autogeneración activada (cada ${AVATAR_AUTOGEN_INTERVAL_SECONDS:-86400}s)" >&2
else
  echo "[avatars] autogeneración desactivada (AVATAR_AUTOGEN_ENABLED=${AVATAR_AUTOGEN_ENABLED:-false}, modelo=${avatar_model})" >&2
fi

exec python manage.py run_ollana_operator \
  --workspace-id "${OLLANA_OPERATOR_WORKSPACE_ID}" \
  --actor-id "${OLLANA_OPERATOR_ACTOR_ID}" \
  --daemon \
  --sleep-seconds "${OLLANA_OPERATOR_SLEEP_SECONDS}" \
  --max-runtime-seconds "${OLLANA_OPERATOR_MAX_RUNTIME_SECONDS}" \
  --holder "render-ollana-operator" \
  "${force_args[@]}"
