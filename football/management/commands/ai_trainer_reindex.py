from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Reindexa tareas de Biblioteca para IA‑Trainer (RAG lexical).'

    def add_arguments(self, parser):
        parser.add_argument('--team-id', type=int, default=0, help='Filtra por Team.id')
        parser.add_argument('--limit', type=int, default=800, help='Máximo de tareas a indexar')
        parser.add_argument('--force', action='store_true', help='Reindexa aunque exista índice')

    def handle(self, *args, **options):
        from django.db.models import Q
        from football.ai_trainer import ai_trainer_index_task
        from football.library_repositories import LIBRARY_MICROCYCLE_MARKER, is_library_session
        from football.models import SessionTask, Team

        team_id = int(options.get('team_id') or 0)
        limit = max(1, min(int(options.get('limit') or 800), 5000))
        force = bool(options.get('force'))

        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).first()
        if not team:
            self.stderr.write('Team no encontrado. Usa --team-id.')
            return

        qs = (
            SessionTask.objects
            .select_related('session__microcycle')
            .filter(session__microcycle__team=team, deleted_at__isnull=True)
            .filter(
                Q(session__microcycle__notes__icontains=LIBRARY_MICROCYCLE_MARKER)
                | Q(session__microcycle__title__istartswith='Biblioteca ')
            )
            .order_by('-id')
        )

        scanned = 0
        indexed = 0
        skipped = 0
        for task in qs.iterator(chunk_size=200):
            if scanned >= limit:
                break
            scanned += 1
            try:
                if not is_library_session(getattr(task, 'session', None)):
                    skipped += 1
                    continue
            except Exception:
                skipped += 1
                continue

            try:
                has_index = bool(getattr(task, 'ai_trainer_index', None))
            except Exception:
                has_index = False
            if has_index and not force:
                skipped += 1
                continue

            idx = ai_trainer_index_task(task, team=team)
            if idx:
                indexed += 1
            else:
                skipped += 1

        self.stdout.write(f'IA‑Trainer reindex: team={team.id} scanned={scanned} indexed={indexed} skipped={skipped} force={force}')
