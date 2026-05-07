from __future__ import annotations

import os

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from football.models import SessionTask, TaskStudioTask, Team
from football.views import (
    _analyze_preview_image_bytes,
    _ensure_library_task_preview,
    _maybe_render_task_preview_server_side,
    _task_scope_for_item,
)


def _looks_like_pitch_only_preview(raw_bytes: bytes) -> bool:
    metrics = _analyze_preview_image_bytes(raw_bytes)
    if not metrics:
        return False
    green_ratio = float(metrics.get("green_ratio") or 0.0)
    white_ratio = float(metrics.get("white_ratio") or 0.0)
    dark_ratio = float(metrics.get("dark_ratio") or 0.0)
    return green_ratio >= 0.88 and white_ratio <= 0.18 and dark_ratio <= 0.35


def _preview_missing_or_broken(name: str) -> bool:
    if not name:
        return True
    try:
        return not bool(default_storage.exists(name))
    except Exception:
        return True


def _check_playwright_chromium() -> str | None:
    """
    Returns an error string if Playwright Chromium cannot be launched, otherwise None.
    """
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return f"Playwright no importable: {exc!r}"
    pw = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(args=["--no-sandbox"])
        browser.close()
        pw.stop()
        return None
    except Exception as exc:
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
        return str(exc)


class Command(BaseCommand):
    help = (
        "Regenera previews (miniaturas) de tareas para que las cards muestren la representación gráfica. "
        "Intenta primero render WYSIWYG server-side (Playwright) y si no, extrae desde PDF."
    )

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=["all", "sessions", "task_studio"], default="sessions")
        parser.add_argument("--team-id", type=int, default=0, help="Filtra por Team.id (solo sesiones).")
        parser.add_argument("--scope", type=str, default="any", help="Filtra por scope (coach/goalkeeper/fitness/abp/any).")
        parser.add_argument("--limit", type=int, default=500, help="Máximo de tareas a procesar.")
        parser.add_argument("--force", action="store_true", help="Regenera aunque la preview parezca OK.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios; solo informa.")

    def handle(self, *args, **options):
        only = str(options.get("only") or "sessions").strip()
        team_id = int(options.get("team_id") or 0)
        scope = str(options.get("scope") or "any").strip().lower()
        limit = max(1, int(options.get("limit") or 500))
        force = bool(options.get("force"))
        dry_run = bool(options.get("dry_run"))

        if scope not in {"any", "coach", "goalkeeper", "fitness", "abp"}:
            self.stdout.write(self.style.WARNING(f"Scope inválido: {scope}. Usando any."))
            scope = "any"

        def iter_targets():
            if only in {"all", "sessions"}:
                qs = SessionTask.objects.select_related("session__microcycle").filter(deleted_at__isnull=True)
                if team_id:
                    qs = qs.filter(session__microcycle__team_id=team_id)
                qs = qs.order_by("-id")[:limit]
                for task in qs:
                    if scope != "any" and _task_scope_for_item(task) != scope:
                        continue
                    yield "sessions", task
            if only in {"all", "task_studio"}:
                qs = TaskStudioTask.objects.filter(deleted_at__isnull=True).order_by("-id")[:limit]
                for task in qs:
                    if scope != "any" and _task_scope_for_item(task) != scope:
                        continue
                    yield "task_studio", task

        if team_id and only not in {"all", "sessions"}:
            self.stdout.write(self.style.WARNING("--team-id solo aplica a sesiones (SessionTask)."))

        if team_id:
            team = Team.objects.filter(id=team_id).first()
            if not team:
                self.stdout.write(self.style.ERROR(f"No existe Team #{team_id}."))
                return
            self.stdout.write(f"Equipo: #{team.id} {team.name}")

        playwright_error = _check_playwright_chromium()
        if playwright_error:
            self.stdout.write(
                self.style.WARNING(
                    "Playwright/Chromium no disponible (se usará fallback desde PDF si existe). "
                    "En Render: activa `INSTALL_PLAYWRIGHT_BROWSERS=true` y despliega con `PLAYWRIGHT_BROWSERS_PATH=0`. "
                    f"Error: {playwright_error}"
                )
            )

        scanned = 0
        regenerated = 0
        skipped = 0
        failed = 0

        for kind, task in iter_targets():
            scanned += 1
            preview_field = getattr(task, "task_preview_image", None)
            preview_name = str(getattr(preview_field, "name", "") or "").strip()

            needs = force or _preview_missing_or_broken(preview_name)
            pitch_only = False
            if not needs and preview_name:
                try:
                    with default_storage.open(preview_name, "rb") as handle:
                        raw = handle.read() or b""
                    if raw and _looks_like_pitch_only_preview(raw):
                        needs = True
                        pitch_only = True
                except Exception:
                    needs = True

            if not needs:
                skipped += 1
                continue

            label = f"{kind}#{int(getattr(task, 'id', 0) or 0)}"
            reason = "force" if force else ("missing" if not preview_name else ("pitch_only" if pitch_only else "broken"))
            self.stdout.write(f"- {label}: regenerate ({reason})")
            if dry_run:
                continue

            ok = False
            if not playwright_error:
                try:
                    ok = bool(_maybe_render_task_preview_server_side(task, force=True))
                except Exception:
                    ok = False

            if not ok and getattr(task, "task_pdf", None):
                try:
                    ok = bool(_ensure_library_task_preview(task, force=True, prefer_render=True))
                except Exception:
                    ok = False

            if ok:
                regenerated += 1
            else:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Regenerate previews: regenerated={regenerated} scanned={scanned} skipped={skipped} failed={failed} dry_run={dry_run}"
            )
        )
