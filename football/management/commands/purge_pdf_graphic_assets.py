from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from football.models import PdfGraphicAsset


class Command(BaseCommand):
    help = "Elimina recursos gráficos (PdfGraphicAsset) del catálogo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all-scopes",
            action="store_true",
            default=False,
            help="No filtra por team/owner (borra en todos los ámbitos).",
        )
        parser.add_argument("--team-id", type=int, default=None, help="Filtra por Team.id (coach/club).")
        parser.add_argument("--owner-id", type=int, default=None, help="Filtra por User.id (Task Studio).")
        parser.add_argument(
            "--include-imported",
            action="store_true",
            default=False,
            help="Incluye assets extraídos de PDFs importados (source_pdf_name no vacío).",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            default=False,
            help="Confirma la eliminación.",
        )

    def handle(self, *args, **options):
        all_scopes = bool(options.get("all_scopes"))
        team_id = options.get("team_id")
        owner_id = options.get("owner_id")
        include_imported = bool(options.get("include_imported"))
        yes = bool(options.get("yes"))

        if not team_id and not owner_id and not all_scopes:
            raise CommandError("Debes indicar --team-id o --owner-id (o usar --all-scopes).")

        qs = PdfGraphicAsset.objects.all()
        if team_id:
            qs = qs.filter(team_id=int(team_id))
        if owner_id:
            qs = qs.filter(owner_id=int(owner_id))
        if not include_imported:
            qs = qs.filter(source_pdf_name="")

        total = qs.count()
        self.stdout.write(self.style.WARNING(f"Assets a eliminar: {total}"))
        if total == 0:
            return
        if not yes:
            raise CommandError("Falta confirmación: añade --yes para borrar.")

        deleted = 0
        for asset in qs.iterator(chunk_size=200):
            try:
                if asset.file:
                    asset.file.delete(save=False)
            except Exception:
                # Si el storage falla, al menos eliminamos el registro.
                pass
            asset.delete()
            deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Eliminados: {deleted}"))
