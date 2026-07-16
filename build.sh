#!/usr/bin/env bash
set -o errexit

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-build-secret-key}"

# Dependencias del sistema para generar PDFs con WeasyPrint (pango/cairo) + fuentes.
# En Render (build command), apt puede fallar por permisos/FS read-only: no bloqueamos el deploy si falla.
if [ "${INSTALL_WEASYPRINT_DEPS:-true}" = "true" ] && command -v apt-get >/dev/null 2>&1; then
  echo "Intentando instalar dependencias de WeasyPrint (pango/cairo) + fuentes..."
  set +o errexit
  WEASY_PKGS="libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libjpeg62-turbo libopenjp2-7 libharfbuzz0b libharfbuzz-subset0 shared-mime-info fontconfig fonts-dejavu-core"
  if [ "$(id -u)" -eq 0 ]; then
    apt-get update || true
    apt-get install -y --no-install-recommends ${WEASY_PKGS} || true
  elif command -v sudo >/dev/null 2>&1; then
    sudo -n apt-get update || true
    sudo -n apt-get install -y --no-install-recommends ${WEASY_PKGS} || true
  else
    apt-get update || true
    apt-get install -y --no-install-recommends ${WEASY_PKGS} || true
  fi
  set -o errexit
fi

# Utilidades del sistema para renderizar previsualizaciones de PDF (pdftoppm).
# En algunos entornos (Render), esto puede requerir permisos de root. No bloqueamos el deploy si falla:
# el sistema hace fallback (previews sin recorte múltiple / o usando imágenes embebidas).
if [ "${INSTALL_POPPLER_UTILS:-true}" = "true" ] && command -v apt-get >/dev/null 2>&1; then
  echo "Intentando instalar poppler-utils (pdftoppm/pdftotext)..."
  # En algunos entornos (Render), el FS de apt puede ser read-only y `apt-get` puede devolver
  # errores que no queremos que corten el build. Desactivamos `errexit` temporalmente.
  set +o errexit
  if [ "$(id -u)" -eq 0 ]; then
    apt-get update || true
    apt-get install -y poppler-utils || true
  elif command -v sudo >/dev/null 2>&1; then
    sudo -n apt-get update || true
    sudo -n apt-get install -y poppler-utils || true
  else
    apt-get update || true
    apt-get install -y poppler-utils || true
  fi
  set -o errexit
fi

python -m pip install --upgrade pip
pip install -r requirements.txt

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required to build the tactical editor frontend." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the tactical editor frontend." >&2
  exit 1
fi

npm --prefix frontend/tactical-editor ci
npm --prefix frontend/tactical-editor run build

for tactical_asset in \
  football/static/football/editor-pro/index.html \
  football/static/football/editor-pro/tactical-editor.js \
  football/static/football/editor-pro/tactical-editor.css
do
  if [ ! -f "${tactical_asset}" ]; then
    echo "Missing tactical editor asset after build: ${tactical_asset}" >&2
    exit 1
  fi
done

_ollama_install_flag="$(echo "${INSTALL_OLLAMA:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${_ollama_install_flag}" = "true" ] || [ "${_ollama_install_flag}" = "1" ] || [ "${_ollama_install_flag}" = "yes" ] || [ "${_ollama_install_flag}" = "on" ]; then
  bash scripts/install_ollama.sh || {
    echo "Aviso: no se pudo instalar Ollama; el deploy continuará sin LLM local." >&2
  }
fi

# Optional: install Playwright browsers for server-side rendering / scraping.
# Enable in Render env with INSTALL_PLAYWRIGHT_BROWSERS=true (or 1/yes/on).
_pw_flag="$(echo "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${_pw_flag}" = "true" ] || [ "${_pw_flag}" = "1" ] || [ "${_pw_flag}" = "yes" ] || [ "${_pw_flag}" = "on" ]; then
  # Important: in platforms like Render, the default Playwright cache path may not persist between
  # build/runtime or across instances. Default to an "hermetic" install path bundled with the app.
  #
  # Users can override by explicitly setting PLAYWRIGHT_BROWSERS_PATH in the service env.
  echo "Instalando navegadores Playwright (chromium, firefox, webkit) con PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-0} ..."
  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}" python -m playwright install chromium firefox webkit
fi

_build_migrate_flag="$(echo "${RUN_MIGRATIONS_AT_BUILD:-false}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ "${_build_migrate_flag}" = "true" ] || [ "${_build_migrate_flag}" = "1" ] || [ "${_build_migrate_flag}" = "yes" ] || [ "${_build_migrate_flag}" = "on" ]; then
  python manage.py migrate --noinput
fi
python manage.py collectstatic --noinput

# Render no crea MEDIA_ROOT por defecto; algunas rutas (fotos/licencias) y healthchecks esperan que exista.
mkdir -p media || true
