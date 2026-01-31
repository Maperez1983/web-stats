#!/usr/bin/env bash
set -euo pipefail

if [ -f manage.py ]; then
  echo "Project already initialized."
  exit 0
fi

python3 -m django startproject webstats .

# Minimal settings tweak for local/dev
python3 - <<'PY'
from pathlib import Path
settings_path = Path('webstats/settings.py')
text = settings_path.read_text()
if "whitenoise" not in text:
    text = text.replace("'django.contrib.staticfiles',", "'django.contrib.staticfiles',\n    'whitenoise.runserver_nostatic',")
if "MIDDLEWARE" in text and "WhiteNoiseMiddleware" not in text:
    text = text.replace("'django.middleware.security.SecurityMiddleware',", "'django.middleware.security.SecurityMiddleware',\n    'whitenoise.middleware.WhiteNoiseMiddleware',")
if "ALLOWED_HOSTS" in text:
    text = text.replace("ALLOWED_HOSTS = []", "ALLOWED_HOSTS = ['*']")
if "DATABASES" in text:
    text += "\nimport dj_database_url\nDATABASES['default'] = dj_database_url.config(default='sqlite:///db.sqlite3', conn_max_age=600)\n"
settings_path.write_text(text)
PY

echo "Initialized Django project in $(pwd)"
