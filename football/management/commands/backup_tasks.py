import json
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from football.models import SessionTask, TaskStudioTask


class Command(BaseCommand):
    help = 'Genera una copia de seguridad JSON de tareas (Sesiones + Task Studio) en el storage por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--only', choices=['all', 'sessions', 'task_studio'], default='all')
        parser.add_argument('--prefix', default='backups/snapshots', help='Carpeta destino dentro del storage')

    def handle(self, *args, **options):
        only = options.get('only') or 'all'
        prefix = str(options.get('prefix') or 'backups/snapshots').strip().strip('/')
        ts = timezone.localtime().strftime('%Y%m%dT%H%M%S')
        payload = {
            'captured_at': timezone.localtime().isoformat(),
            'sessions': [],
            'task_studio': [],
        }
        if only in {'all', 'sessions'}:
            for t in SessionTask.objects.select_related('session').order_by('id'):
                payload['sessions'].append(
                    {
                        'id': t.id,
                        'session_id': t.session_id,
                        'title': t.title,
                        'block': t.block,
                        'duration_minutes': t.duration_minutes,
                        'objective': t.objective,
                        'coaching_points': t.coaching_points,
                        'confrontation_rules': t.confrontation_rules,
                        'status': t.status,
                        'order': t.order,
                        'deleted_at': timezone.localtime(t.deleted_at).isoformat() if t.deleted_at else None,
                        'tactical_layout': t.tactical_layout,
                        'task_pdf': getattr(t.task_pdf, 'name', '') if getattr(t, 'task_pdf', None) else '',
                        'task_preview_image': getattr(t.task_preview_image, 'name', '') if getattr(t, 'task_preview_image', None) else '',
                        'updated_at': timezone.localtime(t.updated_at).isoformat() if getattr(t, 'updated_at', None) else None,
                        'created_at': timezone.localtime(t.created_at).isoformat() if getattr(t, 'created_at', None) else None,
                    }
                )
        if only in {'all', 'task_studio'}:
            for t in TaskStudioTask.objects.select_related('owner', 'workspace').order_by('id'):
                payload['task_studio'].append(
                    {
                        'id': t.id,
                        'workspace_id': t.workspace_id,
                        'owner_id': t.owner_id,
                        'title': t.title,
                        'block': t.block,
                        'duration_minutes': t.duration_minutes,
                        'objective': t.objective,
                        'coaching_points': t.coaching_points,
                        'confrontation_rules': t.confrontation_rules,
                        'status': getattr(t, 'status', ''),
                        'order': getattr(t, 'order', 0),
                        'deleted_at': timezone.localtime(t.deleted_at).isoformat() if getattr(t, 'deleted_at', None) else None,
                        'tactical_layout': t.tactical_layout,
                        'task_pdf': getattr(t.task_pdf, 'name', '') if getattr(t, 'task_pdf', None) else '',
                        'task_preview_image': getattr(t.task_preview_image, 'name', '') if getattr(t, 'task_preview_image', None) else '',
                        'updated_at': timezone.localtime(t.updated_at).isoformat() if getattr(t, 'updated_at', None) else None,
                        'created_at': timezone.localtime(t.created_at).isoformat() if getattr(t, 'created_at', None) else None,
                    }
                )

        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        path = f'{prefix}/{ts}_tasks_{only}.json'
        default_storage.save(path, ContentFile(raw))
        self.stdout.write(self.style.SUCCESS(f'Backup generado: {path}'))

