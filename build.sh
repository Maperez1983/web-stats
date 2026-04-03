#!/usr/bin/env bash
set -o errexit

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-build-secret-key}"

# Utilidades del sistema para renderizar previsualizaciones de PDF (pdftoppm).
# Render (Ubuntu/Debian) permite apt-get durante build.
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y poppler-utils
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
