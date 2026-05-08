import json
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Evalúa rápidamente el dataset exportado (conteos + checks básicos).'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, default='data/ai_trainer/finetune_dataset.jsonl', help='Ruta JSONL')

    def handle(self, *args, **options):
        path = Path(str(options.get('path') or '').strip() or 'data/ai_trainer/finetune_dataset.jsonl')
        if not path.exists():
            self.stderr.write(f'No existe: {path}')
            return

        total = 0
        missing_goal = 0
        missing_title = 0
        short_completion = 0
        bad_json = 0

        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    row = json.loads(line)
                except Exception:
                    bad_json += 1
                    continue
                prompt = row.get('prompt') if isinstance(row.get('prompt'), dict) else {}
                comp = row.get('completion') if isinstance(row.get('completion'), dict) else {}
                goal = str(prompt.get('goal') or '').strip()
                title = str(comp.get('title') or '').strip()
                body = ' '.join([str(comp.get('objective') or ''), str(comp.get('coaching_points') or ''), str(comp.get('rules') or '')]).strip()
                if not goal:
                    missing_goal += 1
                if not title:
                    missing_title += 1
                if len(body) < 80:
                    short_completion += 1

        self.stdout.write(
            'IA‑Trainer dataset eval: '
            f'total={total} bad_json={bad_json} missing_goal={missing_goal} missing_title={missing_title} short_completion={short_completion}'
        )

