#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-dev}"
export ALLOW_SQLITE_IN_PROD="${ALLOW_SQLITE_IN_PROD:-true}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-testserver,localhost,127.0.0.1}"

echo "[qa] Running unit tests…"
python3 manage.py test football

echo "[qa] Running smoke HTTP pages…"
python3 scripts/smoke_http_pages.py

if [[ "${QA_E2E:-0}" == "1" ]]; then
  if command -v node >/dev/null 2>&1; then
    echo "[qa] Running Playwright E2E (optional)…"
    echo "[qa] Tip: set E2E_BASE_URL/E2E_USERNAME/E2E_PASSWORD/E2E_WORKSPACE_ID/E2E_TEAM_ID for full audit."
    node scripts/e2e_pdf_viewer_smoke.js || true
    node scripts/e2e_tacticalpad_smoke.js || true
    node scripts/e2e_roster_cards_smoke.js || true
  else
    echo "[qa] Node not found; skipping Playwright smokes."
  fi
else
  echo "[qa] QA_E2E!=1; skipping Playwright smokes."
fi

echo "[qa] OK"
