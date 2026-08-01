from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from football.library_repositories import (
    TRASH_MICROCYCLE_MARKER,
    TRASH_MICROCYCLE_TITLE,
    TRASH_MICROCYCLE_WEEK_END,
    TRASH_MICROCYCLE_WEEK_START,
    TRASH_SESSION_REASON_PREFIX,
)
from football.models import Team, TrainingMicrocycle, TrainingSession

DEMO_SESSION_CONTENT = "Sesión de ejemplo para un usuario de prueba."


def _is_trash_microcycle(microcycle) -> bool:
    if not microcycle:
        return False
    try:
        if getattr(microcycle, "week_start", None) == TRASH_MICROCYCLE_WEEK_START:
            return True
        notes = str(getattr(microcycle, "notes", "") or "")
        if TRASH_MICROCYCLE_MARKER in notes:
            return True
        title = str(getattr(microcycle, "title", "") or "")
        return title.strip().lower().startswith("papelera")
    except Exception:
        return False


def _get_or_create_trash_microcycle(team):
    if not team:
        return None
    obj = TrainingMicrocycle.objects.filter(team=team, week_start=TRASH_MICROCYCLE_WEEK_START).first()
    if obj:
        changed = False
        if getattr(obj, "week_end", None) != TRASH_MICROCYCLE_WEEK_END:
            obj.week_end = TRASH_MICROCYCLE_WEEK_END
            changed = True
        if str(getattr(obj, "title", "") or "").strip() != TRASH_MICROCYCLE_TITLE:
            obj.title = TRASH_MICROCYCLE_TITLE
            changed = True
        notes = str(getattr(obj, "notes", "") or "")
        if TRASH_MICROCYCLE_MARKER not in notes:
            obj.notes = (notes + "\n" if notes else "") + TRASH_MICROCYCLE_MARKER
            changed = True
        if changed:
            obj.save(update_fields=["title", "week_end", "notes", "updated_at"])
        return obj
    return TrainingMicrocycle.objects.create(
        team=team,
        title=TRASH_MICROCYCLE_TITLE,
        objective="(Sistema) Papelera de sesiones/tareas. No se borra definitivo.",
        week_start=TRASH_MICROCYCLE_WEEK_START,
        week_end=TRASH_MICROCYCLE_WEEK_END,
        status=TrainingMicrocycle.STATUS_DRAFT,
        notes=TRASH_MICROCYCLE_MARKER,
    )


class Command(BaseCommand):
    help = "Mueve a Papelera las sesiones demo sembradas por el bootstrap, sin borrar tareas ni contenido real."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Filtra por Team.id.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios; solo informa.")
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Máximo de sesiones demo a procesar.",
        )

    def handle(self, *args, **options):
        team_id = int(options.get("team_id") or 0)
        dry_run = bool(options.get("dry_run"))
        limit = max(1, int(options.get("limit") or 200))

        teams_qs = Team.objects.all().order_by("id")
        if team_id:
            teams_qs = teams_qs.filter(id=team_id)

        teams = list(teams_qs)
        if not teams:
            self.stdout.write(self.style.ERROR("No se encontraron equipos para limpiar."))
            return

        total_scanned = 0
        total_moved = 0

        for team in teams:
            qs = (
                TrainingSession.objects.select_related("microcycle")
                .filter(
                    microcycle__team=team,
                    content=DEMO_SESSION_CONTENT,
                )
                .order_by("session_date", "order", "id")[:limit]
            )
            if not qs.exists():
                continue

            trash_microcycle = None
            scanned = 0
            moved = 0

            for session in qs:
                scanned += 1
                total_scanned += 1
                if _is_trash_microcycle(getattr(session, "microcycle", None)):
                    continue

                if dry_run:
                    self.stdout.write(
                        f"- team#{team.id} session#{session.id} {session.session_date:%d/%m/%Y} "
                        f"· {session.focus} · microcycle#{getattr(session, 'microcycle_id', 0) or 0}"
                    )
                    moved += 1
                    total_moved += 1
                    continue

                if trash_microcycle is None:
                    trash_microcycle = _get_or_create_trash_microcycle(team)
                if not trash_microcycle:
                    self.stdout.write(self.style.ERROR(f"No se pudo preparar la Papelera para team#{team.id}."))
                    continue

                original_microcycle_id = int(getattr(session, "microcycle_id", 0) or 0)
                focus = str(getattr(session, "focus", "") or "").strip()[:140] or f"Sesión {int(session.id)}"
                marker = f"🗑️ #{int(session.id)}"
                if marker.lower() not in focus.lower():
                    focus = f"{focus} · {marker}"[:140]
                session.microcycle = trash_microcycle
                session.status = TrainingSession.STATUS_CANCELED
                session.workflow_reason = (
                    f"{TRASH_SESSION_REASON_PREFIX} from_mc={original_microcycle_id} "
                    f"by=cleanup_demo_sessions at={timezone.localtime().strftime('%Y-%m-%d %H:%M')}"
                )[:220]
                session.focus = focus
                session.save(update_fields=["microcycle", "status", "workflow_reason", "focus", "updated_at"])
                moved += 1
                total_moved += 1

            self.stdout.write(
                self.style.SUCCESS(f"team#{team.id} {team.name}: scanned={scanned} moved={moved} dry_run={dry_run}")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup demo sessions: teams={len(teams)} scanned={total_scanned} moved={total_moved} "
                f"dry_run={dry_run}"
            )
        )
