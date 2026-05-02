#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-dev}"
export ALLOW_SQLITE_IN_PROD="${ALLOW_SQLITE_IN_PROD:-true}"

TEAM_ID="${TEAM_ID:-1}"

echo "[qa] migrate"
python3 manage.py migrate

echo "[qa] makemigrations --check"
python3 manage.py makemigrations --check --dry-run

echo "[qa] django check"
python3 manage.py check

echo "[qa] smoke system suite"
python3 manage.py smoke_system_suite --team-id "$TEAM_ID"

echo "[qa] audit stats consistency"
python3 manage.py audit_stats_consistency

echo "[qa] unit tests (football)"
python3 manage.py test football

echo "[qa] OK"

