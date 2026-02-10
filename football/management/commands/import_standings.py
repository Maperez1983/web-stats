import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from football.models import ScrapeRun, ScrapeSource
from football.services import update_team_standings


class Command(BaseCommand):
    help = 'Importa una clasificación oficial desde CSV/Excel y actualiza TeamStanding.'

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            type=Path,
            nargs='?',
            default=Path('data/input/rfaf-standings.csv'),
            help='Ruta al CSV que contiene la tabla.',
        )
        parser.add_argument(
            '--competition',
            default='División de Honor Andaluza',
            help='Nombre de la competición (se usará para crear la estructura si no existe).',
        )
        parser.add_argument(
            '--season',
            default='2025/2026',
            help='Temporada a la que pertenecen los datos.',
        )
        parser.add_argument(
            '--group',
            default='Grupo 2',
            help='Nombre del grupo al que pertenece la clasificación.',
        )
        parser.add_argument(
            '--source-name',
            default='Importación manual',
            help='Nombre que se guardará en el historial del botón.',
        )

    def handle(self, *_, **options):
        path: Path = options['path']
        if not path.exists():
            self.stderr.write(f'No existe el archivo {path}')
            return

        source, _ = ScrapeSource.objects.get_or_create(
            name=options['source_name'],
            defaults={'url': path.as_uri(), 'is_active': False},
        )

        with path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
            update_team_standings(
                rows,
                source.name,
                source.url,
                competition_name=options['competition'],
                season_name=options['season'],
                group_name=options['group'],
            )

        run = ScrapeRun.objects.create(
            source=source,
            status=ScrapeRun.Status.SUCCESS,
            message=f'Manual · {path.name}',
            completed_at=timezone.now(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Importados {len(rows)} registros desde {path.name} (run {run.id}).'
            )
        )
