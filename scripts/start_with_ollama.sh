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

exec ./start_asgi.sh
