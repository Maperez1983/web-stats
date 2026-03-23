from django.core.management.base import BaseCommand

from football.models import SessionTask, Team
from football.views import (
    _cleanup_task_joined_text_fields,
    _ensure_library_task_preview,
    _refresh_task_from_pdf_analysis,
    _task_analysis_needs_refresh,
    _task_scope_for_item,
    _task_preview_needs_refresh,
)


class Command(BaseCommand):
    help = "Reanaliza tareas de biblioteca (PDF) con parser PRO, corrige texto y refresca previews."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=None, help="ID de equipo. Si no se indica usa el principal.")
        parser.add_argument("--scope", type=str, default="coach", choices=["coach", "goalkeeper", "fitness", "abp"])
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--force", action="store_true", help="Reanaliza aunque no lo marque como necesario.")

    def handle(self, *args, **options):
        team_id = options.get("team_id")
        scope = str(options.get("scope") or "coach").strip()
        limit = max(1, int(options.get("limit") or 500))
        force = bool(options.get("force"))

        if team_id:
            team = Team.objects.filter(id=team_id).first()
        else:
            team = Team.objects.filter(is_primary=True).first()
        if not team:
            self.stdout.write(self.style.ERROR("No se encontró equipo objetivo."))
            return

        tasks = list(
            SessionTask.objects
            .select_related("session__microcycle")
            .filter(session__microcycle__team=team, task_pdf__isnull=False)
            .order_by("-id")[:limit]
        )
        tasks = [item for item in tasks if _task_scope_for_item(item) == scope]
        self.stdout.write(f"Tareas candidatas: {len(tasks)} · scope={scope} · force={force}")

        refreshed = 0
        text_fixed = 0
        preview_fixed = 0
        skipped = 0
        failed = 0

        for task in tasks:
            try:
                should_refresh = force or _task_analysis_needs_refresh(task)
                task_changed = False
                if should_refresh:
                    if _refresh_task_from_pdf_analysis(task):
                        refreshed += 1
                        task_changed = True
                if _cleanup_task_joined_text_fields(task):
                    text_fixed += 1
                    task_changed = True
                if _task_preview_needs_refresh(task):
                    if _ensure_library_task_preview(task, force=True, prefer_render=True):
                        preview_fixed += 1
                        task_changed = True
                if not task_changed:
                    skipped += 1
            except Exception:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reanálisis PRO completado · refreshed={refreshed} · text_fixed={text_fixed} · "
                f"preview_fixed={preview_fixed} · skipped={skipped} · failed={failed}"
            )
        )
