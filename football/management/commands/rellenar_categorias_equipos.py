"""Rellena `Team.category` a partir del grupo/competición de cada equipo."""

from django.core.management.base import BaseCommand

from football.models import Team
from football.team_category_services import rellenar_categorias


class Command(BaseCommand):
    help = "Deduce y guarda la categoría de los equipos (club por un lado, categoría como sub-id)."

    def add_arguments(self, parser):
        parser.add_argument("--group", type=int, default=None, help="Sólo los equipos de este grupo.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Pisa también las categorías ya escritas (por defecto sólo rellena las vacías).",
        )

    def handle(self, *args, **options):
        qs = Team.objects.select_related("group", "group__season", "group__season__competition")
        if options.get("group"):
            qs = qs.filter(group_id=options["group"])
        equipos = list(qs.order_by("name"))
        resumen = rellenar_categorias(equipos, sobrescribir=bool(options.get("overwrite")))
        for linea in resumen["actualizados"]:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {linea}"))
        if resumen["sin_pistas"]:
            self.stdout.write(
                f"  · sin pistas en su competición ({len(resumen['sin_pistas'])}): "
                + ", ".join(resumen["sin_pistas"][:12])
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(resumen['actualizados'])} actualizados · {len(resumen['ya_tenian'])} ya la tenían "
                f"· {len(resumen['sin_pistas'])} sin pistas."
            )
        )
