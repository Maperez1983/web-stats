"""Importa las plantillas de TODOS los equipos de una competición de laPreferente hacia RivalPlayer.

Ejemplos:
  python manage.py import_rival_league --competition-url https://lapreferente.com/C26717-1/x
  python manage.py import_rival_league --team-id 147 --skip E147   # deriva la comp del equipo, excluye el propio
"""
import re

from django.core.management.base import BaseCommand, CommandError

from football.models import Team
from football.rival_roster_services import import_rival_competition


class Command(BaseCommand):
    help = "Importa las plantillas de todos los rivales de una competición (laPreferente → RivalPlayer)."

    def add_arguments(self, parser):
        parser.add_argument("--competition-url", default="", help="URL de la competición (o de un equipo, se extrae C…)")
        parser.add_argument("--team-id", type=int, default=0, help="Deriva la competición de la preferente_url del equipo")
        parser.add_argument("--season", default="", help="Etiqueta de temporada (ej. 2026/2027)")
        parser.add_argument("--limit", type=int, default=0, help="Máximo de equipos (0 = todos)")
        parser.add_argument("--skip", default="", help="Códigos de equipo a excluir separados por coma (ej. E147)")

    def handle(self, *args, **opts):
        url = (opts.get("competition_url") or "").strip()
        team_id = opts.get("team_id") or 0
        if not url and team_id:
            team = Team.objects.filter(id=team_id).first()
            if not team or not (getattr(team, "preferente_url", "") or "").strip():
                raise CommandError("El equipo no existe o no tiene preferente_url.")
            m = re.search(r"C(\d+)", team.preferente_url)
            if not m:
                raise CommandError("No pude extraer el código de competición de la preferente_url del equipo.")
            url = f"https://lapreferente.com/C{m.group(1)}-1/x"
        if not url:
            raise CommandError("Indica --competition-url o --team-id.")

        limit = opts.get("limit") or None
        skip = [c.strip() for c in (opts.get("skip") or "").split(",") if c.strip()]
        result = import_rival_competition(url, season_label=(opts.get("season") or "").strip(), limit=limit, skip_team_codes=skip)
        t = result["totals"]
        self.stdout.write(self.style.SUCCESS(
            f"Liga importada: equipos={t['teams']} (saltados={t.get('skipped', 0)}, fallidos={t['failed']}) · "
            f"rivales nuevos={t['created']} · actualizados={t['updated']} · reconocidos={t['matched']}"
        ))
        for row in result["teams"]:
            mark = "OK " if row.get("ok") else "FALLO"
            self.stdout.write(f"  {mark} {row.get('name')} (id={row.get('team_id')})")
