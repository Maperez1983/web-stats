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

# Optional: install Playwright browsers for server-side rendering / scraping.
# Enable in Render env with INSTALL_PLAYWRIGHT_BROWSERS=true.
if [ "${INSTALL_PLAYWRIGHT_BROWSERS:-false}" = "true" ]; then
  python -m playwright install chromium
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Render no crea MEDIA_ROOT por defecto; algunas rutas (fotos/licencias) y healthchecks esperan que exista.
mkdir -p media || true
