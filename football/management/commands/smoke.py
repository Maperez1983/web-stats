from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test.utils import get_runner


class Command(BaseCommand):
    help = 'Ejecuta un set rápido de smoke tests (anti-regresión) para flujos críticos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fast',
            action='store_true',
            help='Ejecuta solo tests mínimos (por defecto ya es rápido).',
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity') or 1)
        fast = bool(options.get('fast'))

        # Nota: mantener esta lista pequeña y estable.
        labels = [
            'football.tests.CriticalPagesSmokeTests',
            'football.tests.SessionsAssignTaskSmokeTests',
            'football.tests.MatchdayQuickButtonsTests',
            'football.tests.MatchActionWorkflowTests',
            'football.tests.WorkspaceActiveSelectionTests',
        ]
        if not fast:
            labels.append('football.tests.LoginNextRedirectTests')

        self.stdout.write('Running smoke tests…')
        TestRunner = get_runner(settings)
        runner = TestRunner(verbosity=verbosity, interactive=False)
        failures = runner.run_tests(labels)
        if failures:
            raise SystemExit(failures)
        self.stdout.write(self.style.SUCCESS('Smoke tests OK'))
