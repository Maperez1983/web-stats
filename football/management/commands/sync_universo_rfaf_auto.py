import os
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Sincroniza Universo RFAF de forma automática: login browser + captura snapshot. '
        'Pensado para cron/deploy sin pasos manuales.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--team-url',
            default=os.getenv('RFAF_UNIVERSO_TEAM_URL', '').strip(),
            help='URL de equipo Universo RFAF (recomendado para stats completas de plantilla).',
        )
        parser.add_argument(
            '--storage-state',
            default=str(Path('data') / 'input' / 'rfaf_storage_state.json'),
            help='Ruta del storage_state.',
        )
        parser.add_argument(
            '--capture-out',
            default=str(Path('data') / 'input' / 'universo-rfaf-capture.json'),
            help='Salida de capturas crudas.',
        )
        parser.add_argument(
            '--snapshot-out',
            default=str(Path('data') / 'input' / 'universo-rfaf-snapshot.json'),
            help='Salida snapshot estructurado.',
        )
        parser.add_argument(
            '--wait-ms',
            type=int,
            default=int(os.getenv('RFAF_UNIVERSO_WAIT_MS', '12000') or '12000'),
            help='Espera base tras cada navegación para capturar XHR.',
        )
        parser.add_argument(
            '--manual-browse-ms',
            type=int,
            default=0,
            help='Interacción manual opcional durante captura (normalmente 0 en automático).',
        )
        parser.add_argument('--headed', action='store_true', help='Modo visible (debug).')
        parser.add_argument(
            '--allow-existing-session',
            action='store_true',
            help='Si falla login automático, intenta capturar con storage_state previo.',
        )

    def handle(self, *args, **options):
        username = (os.getenv('RFAF_USER') or '').strip()
        password = (os.getenv('RFAF_PASS') or '').strip()
        if not username or not password:
            raise CommandError('Faltan RFAF_USER / RFAF_PASS para automatizar login.')

        storage_state = options['storage_state']
        headed = bool(options['headed'])

        self.stdout.write('Paso 1/2: login automático Universo RFAF...')
        login_ok = True
        try:
            call_command(
                'test_universo_rfaf_login_browser',
                storage_state=storage_state,
                headed=headed,
            )
        except Exception as exc:
            login_ok = False
            if not options.get('allow_existing_session'):
                raise CommandError(f'Login automático falló: {exc}') from exc
            self.stderr.write(self.style.WARNING(f'Login falló, uso storage_state existente: {exc}'))

        if login_ok:
            self.stdout.write(self.style.SUCCESS('Login automático completado.'))

        self.stdout.write('Paso 2/2: captura de datos Universo RFAF...')
        capture_kwargs = {
            'storage_state': storage_state,
            'capture_out': options['capture_out'],
            'snapshot_out': options['snapshot_out'],
            'wait_ms': int(options['wait_ms']),
            'manual_browse_ms': int(options['manual_browse_ms']),
            'headed': headed,
        }
        team_url = (options.get('team_url') or '').strip()
        if team_url:
            capture_kwargs['team_url'] = team_url

        call_command('capture_universo_rfaf_data', **capture_kwargs)

        self.stdout.write(self.style.SUCCESS('Sincronización automática finalizada.'))
