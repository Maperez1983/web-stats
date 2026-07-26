#!/usr/bin/env bash
#
# Genera el avatar de cada jugador y lo guarda en PRODUCCIÓN (BD Postgres + S3).
#   - Con foto y cara detectable -> face-swap de su cara real.
#   - Sin foto -> avatar sintético (grado de piel + peinado + color de pelo + altura).
# Regenera solo si cambian las entradas, así que es seguro relanzarlo cuando añadas fotos.
#
# USO:
#   1) Una vez:  pip install insightface onnxruntime
#      y tener el modelo inswapper_128.onnx (por defecto ~/ai-image-gen/inswapper_128.onnx).
#   2) Copia la plantilla y rellena TUS credenciales (el fichero está gitignored):
#        cp scripts/avatars.env.example .env.avatars   &&  editar .env.avatars
#   3) Ejecuta:
#        ./scripts/generate_avatars_prod.sh            # todos los jugadores activos
#        ./scripts/generate_avatars_prod.sh --player 42
#        ./scripts/generate_avatars_prod.sh --all --force   # forzar regeneración
#
# OJO: escribe en tu base de datos de producción y sube imágenes a tu S3.
set -euo pipefail
cd "$(dirname "$0")/.."

# Credenciales locales (NO versionadas): DATABASE_URL, USE_S3_MEDIA, AWS_*, AVATAR_INSWAPPER.
if [ -f .env.avatars ]; then
  set -a; . ./.env.avatars; set +a
fi

: "${DATABASE_URL:?Falta DATABASE_URL (Postgres de producción). Defínelo en .env.avatars}"
: "${AWS_STORAGE_BUCKET_NAME:?Faltan las credenciales AWS (USE_S3_MEDIA + AWS_*). Defínelas en .env.avatars}"
export USE_S3_MEDIA="${USE_S3_MEDIA:-true}"
export AVATAR_INSWAPPER="${AVATAR_INSWAPPER:-$HOME/ai-image-gen/inswapper_128.onnx}"

if [ ! -f "$AVATAR_INSWAPPER" ]; then
  echo "No encuentro el modelo inswapper en: $AVATAR_INSWAPPER" >&2
  echo "Define AVATAR_INSWAPPER con la ruta correcta en .env.avatars" >&2
  exit 1
fi

echo "Generando avatares contra producción (S3 + BD)…"
exec python manage.py generate_player_avatars "${@:---all}"
