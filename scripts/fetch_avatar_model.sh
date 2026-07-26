#!/usr/bin/env bash
#
# Descarga el modelo de face-swap (inswapper_128.onnx, ~554 MB) para el cron de avatares.
# Se llama en el buildCommand del cron. Idempotente: si ya está, no lo vuelve a bajar.
# La ruta y el origen son configurables por entorno (AVATAR_INSWAPPER / AVATAR_MODEL_URL).
set -euo pipefail

DEST="${AVATAR_INSWAPPER:-/opt/render/project/src/vendor/inswapper_128.onnx}"
URL="${AVATAR_MODEL_URL:-https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx}"

mkdir -p "$(dirname "$DEST")"
if [ -f "$DEST" ] && [ "$(stat -f%z "$DEST" 2>/dev/null || stat -c%s "$DEST" 2>/dev/null || echo 0)" -gt 500000000 ]; then
  echo "Modelo ya presente: $DEST"
  exit 0
fi

echo "Descargando inswapper_128.onnx -> $DEST"
curl -L -f -s -o "$DEST" "$URL"
echo "OK ($(du -h "$DEST" | cut -f1))"
