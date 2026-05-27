from __future__ import annotations

from django.core.management.base import BaseCommand

from football.models import Team, TrainingSession
from football.session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields


class Command(BaseCommand):
    help = (
        "Limpia campos visibles del plan (warmup/activation/main/cooldown) en sesiones creadas desde PDFs importados "
        "para que la ficha/PDF 'club' mantenga el formato estándar (igual que sesiones creadas manualmente)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Filtra por Team.id (si no, usa el equipo primario).")
        parser.add_argument("--limit", type=int, default=500, help="Máximo de sesiones a procesar.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios; solo informa.")
        parser.add_argument("--clear-objective", action="store_true", help="También vacía `objective`.")
        parser.add_argument("--clear-materials", action="store_true", help="También vacía `materials`.")
        parser.add_argument("--clear-absences", action="store_true", help="También vacía `absences`.")

    def handle(self, *args, **options):
        team_id = int(options.get("team_id") or 0)
        limit = max(1, int(options.get("limit") or 500))
        dry_run = bool(options.get("dry_run"))
        clear_objective = bool(options.get("clear_objective"))
        clear_materials = bool(options.get("clear_materials"))
        clear_absences = bool(options.get("clear_absences"))
        verbosity = int(options.get("verbosity") or 1)

        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).order_by("id").first()
        if not team:
            self.stdout.write(self.style.ERROR("No se encontró equipo. Usa --team-id."))
            return

        self.stdout.write(f"Equipo: #{team.id} {team.name}")

        # Compat: `TrainingSession` no siempre tiene `deleted_at` (depende de rama/migraciones).
        has_deleted_at = False
        try:
            has_deleted_at = any(getattr(f, "name", None) == "deleted_at" for f in TrainingSession._meta.get_fields())
        except Exception:
            has_deleted_at = False
        filters = {"microcycle__team": team, "content__icontains": "imported_doc_id:"}
        if has_deleted_at:
            filters["deleted_at__isnull"] = True
        qs = TrainingSession.objects.select_related("microcycle").filter(**filters).order_by("-id")[:limit]

        scanned = 0
        changed = 0
        skipped = 0

        for session in qs:
            scanned += 1
            fields = parse_session_plan_fields(getattr(session, "content", "") or "")

            agenda_hidden = str(fields.get("agenda_hidden") or "")
            looks_imported = "imported_doc_id:" in agenda_hidden
            if not looks_imported:
                skipped += 1
                continue

            before = {
                "warmup": str(fields.get("warmup") or "").strip(),
                "activation": str(fields.get("activation") or "").strip(),
                "main": str(fields.get("main") or "").strip(),
                "cooldown": str(fields.get("cooldown") or "").strip(),
                "objective": str(fields.get("objective") or "").strip(),
                "materials": str(fields.get("materials") or "").strip(),
                "absences": str(fields.get("absences") or "").strip(),
            }

            needs = any(before[k] for k in ("warmup", "activation", "main", "cooldown"))
            if clear_objective and before["objective"]:
                needs = True
            if clear_materials and before["materials"]:
                needs = True
            if clear_absences and before["absences"]:
                needs = True

            if not needs:
                skipped += 1
                continue

            fields["warmup"] = ""
            fields["activation"] = ""
            fields["main"] = ""
            fields["cooldown"] = ""
            if clear_objective:
                fields["objective"] = ""
            if clear_materials:
                fields["materials"] = ""
            if clear_absences:
                fields["absences"] = ""

            if verbosity >= 2:
                self.stdout.write(
                    f"- session#{session.id}: clean plan fields (dry_run={dry_run})"
                )

            if not dry_run:
                session.content = serialize_session_plan_fields(fields)
                session.save(update_fields=["content"])
            changed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup imported sessions: changed={changed} scanned={scanned} skipped={skipped} dry_run={dry_run}"
            )
        )
