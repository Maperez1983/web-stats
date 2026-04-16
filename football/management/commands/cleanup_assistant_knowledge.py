import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from football.models import AssistantKnowledgeDocument, TaskBlueprint, Team


class Command(BaseCommand):
    help = (
        "Limpia documentos importados del asistente (AssistantKnowledgeDocument) desactivando o borrando los que no "
        "coinciden con un patrón de 'keep'. También elimina los TaskBlueprints asociados."
    )

    def add_arguments(self, parser):
        parser.add_argument("--team-slug", dest="team_slug", help="Slug del equipo (Team.slug).")
        parser.add_argument("--team-id", dest="team_id", type=int, help="ID del equipo (Team.id).")
        parser.add_argument(
            "--keep-regex",
            dest="keep_regex",
            default=r"^(IMG_\d+\.(png|jpg|jpeg|webp)|uefa_.*\.(pdf|txt|md))$",
            help="Regex (sobre doc.title) de lo que quieres conservar. El resto se limpia.",
        )
        parser.add_argument(
            "--hard-delete",
            dest="hard_delete",
            action="store_true",
            default=False,
            help="Borra filas en BD (y el fichero) en vez de solo marcar is_active=False.",
        )
        parser.add_argument(
            "--apply",
            dest="apply",
            action="store_true",
            default=False,
            help="Aplica cambios. Sin esto, solo muestra un resumen (dry-run).",
        )
        parser.add_argument(
            "--max-docs",
            dest="max_docs",
            type=int,
            default=400,
            help="Máximo de documentos a revisar.",
        )

    def handle(self, *args, **options):
        team = self._resolve_team(options)
        keep_regex = str(options.get("keep_regex") or "").strip()
        hard_delete = bool(options.get("hard_delete"))
        apply = bool(options.get("apply"))
        max_docs = int(options.get("max_docs") or 0) or 400

        if not keep_regex:
            raise CommandError("--keep-regex es obligatorio.")
        try:
            keep_re = re.compile(keep_regex, flags=re.IGNORECASE)
        except re.error as exc:
            raise CommandError(f"Regex inválida en --keep-regex: {exc}") from exc

        docs = list(
            AssistantKnowledgeDocument.objects.filter(team=team).order_by("-created_at", "-id")[:max_docs]
        )
        if not docs:
            raise CommandError("No hay documentos para este equipo.")

        keep = []
        purge = []
        for d in docs:
            title = str(d.title or "").strip()
            if keep_re.match(title):
                keep.append(d)
            else:
                purge.append(d)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Equipo: {team.name} (slug={team.slug}, id={team.id}) · docs={len(docs)} "
                f"keep={len(keep)} purge={len(purge)} apply={apply} hard_delete={hard_delete}"
            )
        )

        if not purge:
            self.stdout.write(self.style.SUCCESS("Nada que limpiar."))
            return

        # Muestra ejemplo de lo que se limpiaría.
        sample = [str(d.title or "") for d in purge[:25]]
        self.stdout.write("Se limpiarán (muestra):")
        for s in sample:
            self.stdout.write(f"- {s}")
        if len(purge) > len(sample):
            self.stdout.write(f"... +{len(purge) - len(sample)} más")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run: ejecuta con --apply para aplicar la limpieza."))
            return

        deactivated = 0
        deleted = 0
        bp_deleted = 0
        with transaction.atomic():
            for d in purge:
                # Borra blueprints generados desde este doc.
                qs_bp = TaskBlueprint.objects.filter(team=team, payload__meta__source_doc_id=int(d.id))
                qs_bp = qs_bp.filter(created_by__startswith="assistant_docs")
                bp_deleted += int(qs_bp.count() or 0)
                qs_bp.delete()

                if hard_delete:
                    try:
                        d.file.delete(save=False)
                    except Exception:
                        pass
                    d.delete()
                    deleted += 1
                else:
                    if d.is_active:
                        d.is_active = False
                        d.save(update_fields=["is_active"])
                        deactivated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"OK · blueprints_deleted={bp_deleted} deactivated={deactivated} deleted={deleted}"
            )
        )

    def _resolve_team(self, options):
        team_id = options.get("team_id")
        team_slug = str(options.get("team_slug") or "").strip()
        if not team_id and not team_slug:
            raise CommandError("Indica --team-id o --team-slug.")
        if team_id:
            team = Team.objects.filter(id=int(team_id)).first()
        else:
            team = Team.objects.filter(slug=team_slug).first()
        if not team:
            raise CommandError("No se encontró el equipo indicado.")
        return team

