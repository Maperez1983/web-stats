import json
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Exporta dataset JSONL para fine‑tuning (fase 3) a partir de tareas guardadas por IA‑Trainer.'

    def add_arguments(self, parser):
        parser.add_argument('--team-id', type=int, default=0, help='Filtra por Team.id')
        parser.add_argument('--out', type=str, default='data/ai_trainer/finetune_dataset.jsonl', help='Ruta de salida JSONL')
        parser.add_argument('--limit', type=int, default=2000, help='Máximo de ejemplos')

    def handle(self, *args, **options):
        from football.library_repositories import LIBRARY_REPOSITORY_AI_TRAINER
        from football.models import SessionTask, Team

        team_id = int(options.get('team_id') or 0)
        limit = max(1, min(int(options.get('limit') or 2000), 20000))
        out_path = Path(str(options.get('out') or '').strip() or 'data/ai_trainer/finetune_dataset.jsonl')
        out_path.parent.mkdir(parents=True, exist_ok=True)

        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).first()
        if not team:
            self.stderr.write('Team no encontrado. Usa --team-id.')
            return

        def _task_meta(task):
            try:
                layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
                meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
                return meta if isinstance(meta, dict) else {}
            except Exception:
                return {}

        qs = (
            SessionTask.objects
            .select_related('session__microcycle')
            .filter(session__microcycle__team=team, deleted_at__isnull=True)
            .order_by('-id')
        )

        exported = 0
        with out_path.open('w', encoding='utf-8') as f:
            for task in qs.iterator(chunk_size=200):
                if exported >= limit:
                    break
                meta = _task_meta(task)
                if str(meta.get('repository') or '') != LIBRARY_REPOSITORY_AI_TRAINER:
                    continue
                ai = meta.get('ai_trainer') if isinstance(meta.get('ai_trainer'), dict) else {}
                goal = str(ai.get('goal') or getattr(task, 'objective', '') or '').strip()
                profile = str(ai.get('profile') or '').strip() or 'hybrid'
                phase = str(ai.get('phase') or '').strip()

                # Formato genérico (independiente de proveedor). Luego podrás mapearlo a OpenAI / otros.
                prompt = {
                    'profile': profile,
                    'phase': phase,
                    'goal': goal,
                }
                completion = {
                    'title': str(getattr(task, 'title', '') or '').strip(),
                    'objective': str(getattr(task, 'objective', '') or '').strip(),
                    'coaching_points': str(getattr(task, 'coaching_points', '') or '').strip(),
                    'rules': str(getattr(task, 'confrontation_rules', '') or '').strip(),
                }
                row = {
                    'id': int(getattr(task, 'id', 0) or 0),
                    'team_id': int(team.id),
                    'prompt': prompt,
                    'completion': completion,
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                exported += 1

        self.stdout.write(f'IA‑Trainer finetune export: team={team.id} exported={exported} out={str(out_path)}')
