from __future__ import annotations

import os
from typing import Any, Dict

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """
    Healthcheck ligero para balanceadores (Render).

    - No requiere auth.
    - No expone secretos.
    - Intenta validar conectividad DB + migraciones + media root.
    """
    payload: Dict[str, Any] = {
        "ok": True,
        "ts": timezone.now().isoformat(),
        "checks": {},
    }

    checks: Dict[str, Any] = {}

    # --- DB connectivity ---
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
        payload["ok"] = False

    # --- Pending migrations (best-effort) ---
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            checks["migrations"] = "pending"
            payload["ok"] = False
        else:
            checks["migrations"] = "ok"
    except Exception:
        # No bloquear healthcheck por incapacidad de inspeccionar migraciones.
        checks["migrations"] = "unknown"

    # --- Media root (uploads) ---
    try:
        media_root = str(getattr(settings, "MEDIA_ROOT", "") or "").strip()
        if not media_root:
            checks["media_root"] = "unset"
        else:
            exists = os.path.isdir(media_root)
            writable = os.access(media_root, os.W_OK) if exists else False
            checks["media_root"] = "ok" if (exists and writable) else "not_writable"
    except Exception:
        checks["media_root"] = "unknown"

    payload["checks"] = checks
    return JsonResponse(payload, status=200 if payload.get("ok") else 503)

