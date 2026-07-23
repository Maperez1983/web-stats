"""
Spike de viabilidad: ¿puede el servidor leer la clasificación en vivo de La Preferente?

NO escribe nada en la BD. Solo baja una URL de La Preferente con la sesión anti-bot que ya
usamos para rosters (`_fetch_preferente_response`), intenta localizar la tabla de clasificación
y reporta qué pasó: status HTTP, señales de Cloudflare/CAPTCHA, si hay tabla y cuántas filas.

Uso:
    python manage.py preferente_standings_probe --url "https://www.lapreferente.com/.../clasificacion"
    python manage.py preferente_standings_probe --team <team_id>   # usa Team.preferente_url

Sirve para decidir si merece la pena cablear La Preferente al sync de competición o si, como
sospechamos, viene bloqueada servidor->Preferente y hay que ir por el navegador in-app.
"""

from django.core.management.base import BaseCommand, CommandError

# Marcadores típicos de muro anti-bot (Cloudflare / captcha) en el HTML devuelto.
_BLOCK_MARKERS = (
    'just a moment',
    'attention required',
    'cf-browser-verification',
    'cf-challenge',
    'captcha',
    'recaptcha',
    'hcaptcha',
    'enable javascript and cookies',
    '__cf_chl',
)


class Command(BaseCommand):
    help = 'Diagnostica si el servidor puede leer la clasificación en vivo de La Preferente (no escribe nada).'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='', help='URL de clasificación/equipo en lapreferente.com.')
        parser.add_argument('--team', dest='team_id', default='', help='ID de Team; usa su preferente_url.')
        parser.add_argument('--dump', action='store_true', help='Vuelca los primeros 1200 caracteres del HTML.')

    def handle(self, *args, **options):
        from bs4 import BeautifulSoup

        from football.management.commands.scrape_preferente import Command as ScrapeCommand
        from football.models import Team
        from football.services import _fetch_preferente_response

        url = str(options.get('url') or '').strip()
        team_id = str(options.get('team_id') or '').strip()
        if not url and team_id:
            team = Team.objects.filter(pk=team_id).first()
            if not team:
                raise CommandError(f'No existe Team con id={team_id}.')
            url = str(getattr(team, 'preferente_url', '') or '').strip()
            if not url:
                raise CommandError(f'El Team {team_id} ({team.name}) no tiene preferente_url configurada.')
            self.stdout.write(f'Team {team_id}: {team.name}')
        if not url:
            raise CommandError('Indica --url o --team.')

        self.stdout.write(f'GET {url}')
        try:
            response = _fetch_preferente_response(url)
        except Exception as exc:  # noqa: BLE001 — el spike debe reportar el fallo, no reventar.
            self.stdout.write(self.style.ERROR(f'VEREDICTO: ERROR_RED — {type(exc).__name__}: {exc}'))
            return

        status = response.status_code
        html = response.text or ''
        lowered = html.lower()
        self.stdout.write(f'HTTP {status} · {len(html)} bytes · content-type={response.headers.get("Content-Type", "?")}')

        blocked_markers = [m for m in _BLOCK_MARKERS if m in lowered]

        table = None
        rows = 0
        sample = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = ScrapeCommand.find_standings_table(soup)
            if table is not None:
                data_rows = table.find_all('tr')[1:]
                for row in data_rows:
                    cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                    if len(cells) >= 2 and any(cells):
                        rows += 1
                        if len(sample) < 3:
                            sample.append(' | '.join(cells[:6]))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f'Parseo falló: {type(exc).__name__}: {exc}'))

        if options.get('dump'):
            self.stdout.write('--- HTML[:1200] ---')
            self.stdout.write(html[:1200])
            self.stdout.write('--- /HTML ---')

        # Veredicto.
        if status in {403, 429, 503} or blocked_markers:
            reason = f'HTTP {status}' if status in {403, 429, 503} else ''
            if blocked_markers:
                reason = (reason + ' + ' if reason else '') + f'marcadores={blocked_markers}'
            self.stdout.write(self.style.ERROR(f'VEREDICTO: BLOQUEADO ({reason}). Preferente no legible servidor->web.'))
            return
        if status != 200:
            self.stdout.write(self.style.WARNING(f'VEREDICTO: HTTP inesperado {status}. Revisar URL o web.'))
            return
        if table is None:
            self.stdout.write(
                self.style.WARNING(
                    'VEREDICTO: SIN_TABLA. 200 OK pero no se localizó la clasificación (¿URL de equipo en vez de '
                    'clasificación? ¿estructura HTML distinta?). Usa --dump para inspeccionar.'
                )
            )
            return
        if rows == 0:
            self.stdout.write(self.style.WARNING('VEREDICTO: TABLA_VACIA. Tabla encontrada pero sin filas de datos.'))
            return

        self.stdout.write(self.style.SUCCESS(f'VEREDICTO: OK — clasificación legible, {rows} equipos.'))
        for line in sample:
            self.stdout.write(f'  · {line}')
