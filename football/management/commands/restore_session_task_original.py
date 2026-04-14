from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from football.models import SessionTask


def _restore_from_original_snapshot(task: SessionTask) -> None:
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta = dict(meta)
    original = meta.get('original_version') if isinstance(meta.get('original_version'), dict) else {}
    if not original:
        raise CommandError('La tarea no tiene versión original guardada (meta.original_version vacío).')

    task.title = str(original.get('title') or task.title or '')[:160]
    block = str(original.get('block') or task.block or SessionTask.BLOCK_MAIN_1).strip()
    valid_blocks = {choice[0] for choice in SessionTask.BLOCK_CHOICES}
    if block not in valid_blocks:
        block = SessionTask.BLOCK_MAIN_1
    task.block = block
    duration = original.get('duration_minutes')
    try:
        duration = int(duration)
    except Exception:
        duration = int(task.duration_minutes or 15)
    task.duration_minutes = max(5, min(duration, 90))
    task.objective = str(original.get('objective') or '')[:180]
    task.coaching_points = str(original.get('coaching_points') or '')
    task.confrontation_rules = str(original.get('confrontation_rules') or '')

    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    analysis_meta = dict(analysis_meta)
    original_sheet = original.get('task_sheet') if isinstance(original.get('task_sheet'), dict) else {}
    if original_sheet:
        analysis_meta['task_sheet'] = dict(original_sheet)
        meta['analysis'] = analysis_meta

    original_graphic = original.get('graphic_editor') if isinstance(original.get('graphic_editor'), dict) else {}
    if original_graphic:
        meta['graphic_editor'] = dict(original_graphic)

    layout['meta'] = meta
    task.tactical_layout = layout

    preview_name = str(original.get('task_preview_image') or '').strip()
    update_fields = [
        'title',
        'block',
        'duration_minutes',
        'objective',
        'coaching_points',
        'confrontation_rules',
        'tactical_layout',
    ]
    if preview_name:
        task.task_preview_image = preview_name
        update_fields.append('task_preview_image')
    task.save(update_fields=update_fields)


class Command(BaseCommand):
    help = 'Restaura una tarea de sesiones (SessionTask) desde su snapshot original (meta.original_version).'

    def add_arguments(self, parser):
        parser.add_argument('--task-id', type=int, required=True, help='ID de la tarea (SessionTask.id)')
        parser.add_argument('--dry-run', action='store_true', help='Muestra qué haría sin guardar cambios')

    def handle(self, *args, **options):
        task_id = int(options['task_id'])
        dry_run = bool(options.get('dry_run'))

        task = SessionTask.objects.select_related('session').filter(id=task_id).first()
        if not task:
            raise CommandError('Tarea no encontrada.')

        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        original = meta.get('original_version') if isinstance(meta.get('original_version'), dict) else {}
        if not original:
            raise CommandError('La tarea no tiene versión original guardada. No hay nada que restaurar.')

        before = {
            'title': task.title,
            'objective_len': len(task.objective or ''),
            'coaching_len': len(task.coaching_points or ''),
            'rules_len': len(task.confrontation_rules or ''),
        }
        after = {
            'title': str(original.get('title') or task.title or '')[:160],
            'objective_len': len(str(original.get('objective') or '')),
            'coaching_len': len(str(original.get('coaching_points') or '')),
            'rules_len': len(str(original.get('confrontation_rules') or '')),
        }

        self.stdout.write(
            'Resumen restauración:\n'
            f"- task: #{task.id} ({task.title})\n"
            f"- session: #{task.session_id} ({getattr(task.session, 'focus', '')})\n"
            f"- captured_at: {original.get('captured_at') or 'n/a'}\n"
            f"- before: {before}\n"
            f"- after: {after}\n"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: no se guardaron cambios.'))
            return

        _restore_from_original_snapshot(task)
        self.stdout.write(self.style.SUCCESS(f'Restaurada tarea #{task.id} ({timezone.localtime().isoformat()}).'))

