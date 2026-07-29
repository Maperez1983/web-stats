"""Importa la plantilla de un equipo RIVAL desde laPreferente hacia RivalPlayer (aislado).

Ejemplos:
  python manage.py import_rival_squad --url https://lapreferente.com/E282C26717-1/cd-rincon --name "C.D. Rincón"
  python manage.py import_rival_squad --url <url> --name <n> --html-file /tmp/rincon.html   # offline
  python manage.py import_rival_squad --team-id 123   # equipo ya existente con preferente_url
"""
from django.core.management.base import BaseCommand, CommandError

from football.models import Team, resolve_or_create_team
from football.rival_roster_services import import_rival_squad, parse_rival_squad


class Command(BaseCommand):
    help = "Importa la plantilla de un equipo rival desde laPreferente (modelo RivalPlayer, aislado)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default="", help="URL del equipo en laPreferente")
        parser.add_argument("--name", default="", help="Nombre del equipo rival (para crearlo si no existe)")
        parser.add_argument("--team-id", type=int, default=0, help="Id de un Team ya existente (usa su preferente_url)")
        parser.add_argument("--html-file", default="", help="Ruta a un HTML ya descargado (evita la red)")
        parser.add_argument("--season", default="", help="Etiqueta de temporada (ej. 2026/2027)")

    def handle(self, *args, **opts):
        url = (opts.get("url") or "").strip()
        name = (opts.get("name") or "").strip()
        team_id = opts.get("team_id") or 0
        html_file = (opts.get("html_file") or "").strip()
        season = (opts.get("season") or "").strip()

        # Resolver el equipo rival (dedup por preferente_url / nombre).
        if team_id:
            team = Team.objects.filter(id=team_id).first()
            if not team:
                raise CommandError(f"No existe Team id={team_id}")
            url = url or (getattr(team, "preferente_url", "") or "")
        else:
            if not url:
                raise CommandError("Indica --url (o --team-id).")
            team, created = resolve_or_create_team(name=name or url, preferente_url=url)
            self.stdout.write(f"Equipo rival: {team.display_name} (id={team.id}) {'[creado]' if created else '[existente]'}")

        # Obtener el HTML (fichero offline o red, con el manejo de 403/fallback del servicio).
        if html_file:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as fh:
                html = fh.read()
        else:
            from football.services import _fetch_preferente_response

            resp = _fetch_preferente_response(url, timeout=25)
            if getattr(resp, "status_code", None) == 403:
                raise CommandError("laPreferente devolvió 403. Reintenta más tarde o usa --html-file con el HTML pegado.")
            resp.raise_for_status()
            html = resp.text

        rows = parse_rival_squad(html)
        if not rows:
            raise CommandError("No se encontraron jugadores en la plantilla (¿HTML parcial o estructura distinta?).")

        result = import_rival_squad(team, rows, season_label=season)
        self.stdout.write(self.style.SUCCESS(
            f"Plantilla importada: {len(rows)} jugadores · "
            f"nuevos={result['created']} · actualizados={result['updated']} · "
            f"bajas={result['deactivated']} · reconocidos={result['matched']}"
        ))
