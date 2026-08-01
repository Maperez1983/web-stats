"""Trae de Universo RFAF el terreno de juego de los equipos y lo guarda en su ficha."""

from django.core.management.base import BaseCommand

from football.models import Team
from football.universo_venue_services import sincronizar_campos_de_equipos


class Command(BaseCommand):
    help = "Rellena campo de juego, dirección y enlace de mapa de los equipos desde Universo RFAF."

    def add_arguments(self, parser):
        parser.add_argument("--group", type=int, default=None, help="Sólo los equipos de este grupo.")
        parser.add_argument("--team", type=int, default=None, help="Sólo este equipo.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Corrige también lo que ya estuviera puesto (por defecto sólo rellena huecos).",
        )

    def handle(self, *args, **options):
        qs = Team.objects.all()
        if options.get("team"):
            qs = qs.filter(id=options["team"])
        elif options.get("group"):
            qs = qs.filter(group_id=options["group"])
        equipos = list(qs.order_by("name"))
        if not equipos:
            self.stdout.write(self.style.WARNING("No hay equipos que encajen con el filtro."))
            return

        resumen = sincronizar_campos_de_equipos(equipos, sobrescribir=bool(options.get("overwrite")))
        for linea in resumen["actualizados"]:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {linea}"))
        for linea in resumen["sin_datos"]:
            self.stdout.write(f"  · sin campo en Universo: {linea}")
        for linea in resumen["sin_codigo"]:
            self.stdout.write(f"  · sin código de Universo: {linea}")
        for linea in resumen["errores"]:
            self.stdout.write(self.style.ERROR(f"  ✗ {linea}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(resumen['actualizados'])} equipos actualizados de {len(equipos)}."
            )
        )
