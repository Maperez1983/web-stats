#!/usr/bin/env bash
# Servidor de desarrollo local (iterar sin desplegar).
# Con DEBUG=True los estaticos NO pasan por el manifest, asi que no hace falta
# collectstatic; y ALLOW_SQLITE_IN_PROD deja usar la db.sqlite3 local.
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBUG=True
export SECRET_KEY=dev-local
export ALLOW_SQLITE_IN_PROD=true
# Token de prueba SOLO local: permite ensayar el agente de rivales contra este servidor.
export RIVAL_INGEST_TOKEN="${RIVAL_INGEST_TOKEN:-token-solo-local}"
export DJANGO_SETTINGS_MODULE=webstats.settings
exec python3 manage.py runserver 8010 --noreload
