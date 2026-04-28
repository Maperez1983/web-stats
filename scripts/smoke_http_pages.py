#!/usr/bin/env python3
"""
Smoke test sin navegador para detectar regresiones (errores 500) en pantallas críticas.

Uso (local):
  DEBUG=true SECRET_KEY=dev ALLOW_SQLITE_IN_PROD=true ALLOWED_HOSTS=testserver,localhost,127.0.0.1 \
    .venv/bin/python scripts/smoke_http_pages.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlencode


def _setup_django() -> None:
    # Asegura que el root del proyecto está en sys.path (cuando se ejecuta desde /scripts).
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webstats.settings")
    os.environ.setdefault("DEBUG", os.getenv("DEBUG", "true"))
    os.environ.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev"))
    os.environ.setdefault("ALLOW_SQLITE_IN_PROD", os.getenv("ALLOW_SQLITE_IN_PROD", "true"))
    os.environ.setdefault("ALLOWED_HOSTS", os.getenv("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1"))
    import django  # noqa: WPS433

    django.setup()


def _pick_team_id() -> int:
    from football.models import Team  # noqa: WPS433

    team = Team.objects.filter(is_primary=True).order_by("id").first() or Team.objects.order_by("id").first()
    return int(getattr(team, "id", 0) or 0)


def _pick_user():
    from django.contrib.auth import get_user_model  # noqa: WPS433

    User = get_user_model()
    return User.objects.filter(is_superuser=True).order_by("id").first() or User.objects.order_by("id").first()


def _urls(team_id: int) -> list[str]:
    qs = urlencode({"team": team_id})
    return [
        "/",
        f"/coach/sesiones/?{qs}",
        f"/coach/sesiones/?{qs}&tab=sessions",
        f"/coach/sesiones/?{qs}&tab=library&library_view=overview",
        f"/coach/sesiones/?{qs}&tab=library&library_view=source&library_key=imported",
        f"/coach/sesiones/?{qs}&tab=import",
        f"/coach/plantilla/?{qs}",
        f"/convocatoria/?{qs}",
        f"/11-inicial/?{qs}",
        f"/registro-acciones/?{qs}",
        f"/analysis/?{qs}",
        f"/kpi/explorer/?{qs}",
    ]


def main() -> int:
    _setup_django()
    from django.test import Client  # noqa: WPS433

    team_id = _pick_team_id()
    user = _pick_user()
    if not user:
        print("[smoke] FAIL: no hay usuarios en la base de datos", file=sys.stderr)
        return 2
    if not team_id:
        print("[smoke] FAIL: no hay equipos en la base de datos", file=sys.stderr)
        return 2

    client = Client()
    client.force_login(user)
    failed: list[tuple[str, int]] = []
    for url in _urls(team_id):
        try:
            resp = client.get(url)
        except Exception as exc:  # pragma: no cover
            print(f"[smoke] EXC {url}: {exc}", file=sys.stderr)
            failed.append((url, 599))
            continue
        status = int(getattr(resp, "status_code", 0) or 0)
        ok = status < 500
        print(f"[smoke] {status} {url}")
        if not ok:
            failed.append((url, status))

    if failed:
        print("[smoke] FAIL (500+):", file=sys.stderr)
        for url, status in failed:
            print(f"  - {status} {url}", file=sys.stderr)
        return 1

    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
