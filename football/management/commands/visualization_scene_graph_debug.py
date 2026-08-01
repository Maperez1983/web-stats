from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from football.models import SessionTask
from football.visualization_engine import write_scene_graph_debug_html


class Command(BaseCommand):
    help = 'Genera un HTML autónomo para inspeccionar el Scene Graph de una tarea.'

    def add_arguments(self, parser):
        parser.add_argument('--task', type=int, required=True, help='ID de SessionTask.')
        parser.add_argument('--out', type=str, default='', help='Ruta opcional de salida para el HTML.')

    def handle(self, *args, **options):
        task_id = int(options['task'])
        out_raw = str(options.get('out') or '').strip()

        task = (
            SessionTask.objects
            .select_related('session')
            .filter(id=task_id)
            .first()
        )
        if not task:
            raise CommandError(f'No existe SessionTask #{task_id}.')

        out_path = Path(out_raw).expanduser() if out_raw else (Path.home() / 'Downloads' / 'scene_graph_debug.html')
        written_path = write_scene_graph_debug_html(task, out_path=out_path)
        self.stdout.write(self.style.SUCCESS(str(written_path)))
