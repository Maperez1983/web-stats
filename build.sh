#!/usr/bin/env bash
set -o errexit

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-build-secret-key}"

# Utilidades del sistema para renderizar previsualizaciones de PDF (pdftoppm).
# En algunos entornos (Render), esto puede requerir permisos de root. No bloqueamos el deploy si falla:
# el sistema hace fallback (previews sin recorte múltiple / o usando imágenes embebidas).
if [ "${INSTALL_POPPLER_UTILS:-true}" = "true" ] && command -v apt-get >/dev/null 2>&1; then
  echo "Intentando instalar poppler-utils (pdftoppm/pdftotext)..."
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
fi

python -m pip install --upgrade pip
pip install -r requirements.txt

# Optional: install Playwright browsers for server-side rendering / scraping.
# Enable in Render env with INSTALL_PLAYWRIGHT_BROWSERS=true.
if [ "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" = "true" ]; then
  python -m playwright install chromium
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
