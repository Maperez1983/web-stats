#!/usr/bin/env bash
set -euo pipefail

if command -v ollama >/dev/null 2>&1; then
  ollama --version || true
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[build] curl is not available; cannot install Ollama." >&2
  exit 1
fi

echo "[build] Installing Ollama..." >&2
curl -fsSL https://ollama.com/install.sh | sh
ollama --version || true
