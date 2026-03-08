from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from football.models import Team


class Command(BaseCommand):
    help = "Descarga y guarda la plantilla de La Preferente en data/input/player-roster.html."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="",
            help="URL de equipo en La Preferente. Si se omite, usa la del equipo principal.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Timeout de descarga en segundos (por defecto 30).",
        )

    def handle(self, *args, **options):
        url = (options.get("url") or "").strip()
        timeout = options["timeout"]
        primary_team = Team.objects.filter(is_primary=True).first()

        if not url:
            if primary_team and primary_team.preferente_url:
                url = primary_team.preferente_url.strip()
            else:
                raise CommandError(
                    "No hay URL disponible. Pasa --url o guarda preferente_url en el equipo principal."
                )

        headers = {
            "User-Agent": "webstats-crm/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9",
        }
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"No se pudo descargar la plantilla desde {url}: {exc}") from exc

        destination = Path(settings.BASE_DIR) / "data" / "input" / "player-roster.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(response.text, encoding="utf-8")

        if primary_team and primary_team.preferente_url != url:
            primary_team.preferente_url = url
            primary_team.save(update_fields=["preferente_url"])

        self.stdout.write(self.style.SUCCESS(f"Plantilla guardada en {destination}"))
