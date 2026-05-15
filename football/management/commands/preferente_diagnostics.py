import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Diagnóstico de La Preferente: resuelve URL, prueba HTML y fallback JSON, y muestra errores detallados.'

    def add_arguments(self, parser):
        parser.add_argument('--team-id', type=int, default=0, help='ID del equipo (football.Team)')
        parser.add_argument('--team-name', default='', help='Nombre del equipo (para resolver URL)')
        parser.add_argument('--team-url', default='', help='URL directa de La Preferente (si ya la conoces)')

    def handle(self, *args, **options):
        from football.models import Team
        from football.services import (
            _extract_preferente_team_id,
            _fetch_preferente_response,
            _fetch_preferente_team_roster_via_json,
            fetch_preferente_team_roster,
            find_preferente_team_url,
            parse_preferente_roster,
        )

        team_id = int(options.get('team_id') or 0)
        team_name = str(options.get('team_name') or '').strip()
        team_url = str(options.get('team_url') or '').strip()

        team = None
        if team_id:
            team = Team.objects.filter(id=team_id).first()
            if not team:
                raise CommandError(f'No existe Team con id={team_id}')
            if not team_name:
                team_name = str(getattr(team, 'name', '') or '').strip()
            if not team_url:
                team_url = str(getattr(team, 'preferente_url', '') or '').strip()

        if not team_url and team_name:
            team_url = find_preferente_team_url(team_name)

        if not team_url:
            raise CommandError('No se pudo resolver URL. Pasa --team-url o --team-name/--team-id.')

        self.stdout.write('== La Preferente diagnostics ==')
        if team:
            self.stdout.write(f'Team: {team.id} · {team.name}')
        self.stdout.write(f'URL: {team_url}')

        preferente_id = _extract_preferente_team_id(team_url)
        self.stdout.write(f'IDequipo: {preferente_id or "(no-detectado)"}')

        # 1) Raw fetch
        try:
            resp = _fetch_preferente_response(team_url, timeout=25)
            self.stdout.write(f'HTTP status: {getattr(resp, "status_code", None)}')
            self.stdout.write(f'Content-Type: {resp.headers.get("content-type", "") if getattr(resp, "headers", None) else ""}')
            html = resp.text or ''
            self.stdout.write(f'HTML length: {len(html)}')
            try:
                parsed = parse_preferente_roster(html)
            except Exception as exc:
                parsed = []
                self.stdout.write(self.style.ERROR(f'parse_preferente_roster error: {type(exc).__name__}: {exc}'))
            self.stdout.write(f'Parsed roster (HTML): {len(parsed)} jugadores')
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'_fetch_preferente_response error: {type(exc).__name__}: {exc}'))
            html = ''
            parsed = []

        # 2) JSON fallback
        if preferente_id and str(preferente_id).isdigit():
            try:
                json_roster = _fetch_preferente_team_roster_via_json(preferente_id)
                self.stdout.write(f'Parsed roster (JSON fallback): {len(json_roster)} jugadores')
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'_fetch_preferente_team_roster_via_json error: {type(exc).__name__}: {exc}'))

        # 3) High-level function (what app uses)
        try:
            roster = fetch_preferente_team_roster(team_url)
            self.stdout.write(self.style.SUCCESS(f'fetch_preferente_team_roster -> {len(roster)} jugadores'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'fetch_preferente_team_roster error: {type(exc).__name__}: {exc}'))

