"""
Refresco periódico de la clasificación/próximo rival de TODOS los clubes dados de alta.

La portada del entrenador solo lee el último snapshot; el snapshot se refresca al sincronizar.
Sin un proceso automático, la clasificación se quedaría con los datos del último sync manual.
Este comando recorre cada contexto competitivo de club y re-sincroniza (Universo o La Preferente
según el provider de cada equipo), pensado para lanzarse por cron sin intervención.

Cubre a todos los equipos: hay un WorkspaceCompetitionContext por (workspace, equipo), así que
iterar los contextos activos sincroniza cada categoría de cada club.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from football.competition_sync import sync_workspace_competition_context
from football.models import Workspace, WorkspaceCompetitionContext


class Command(BaseCommand):
    help = 'Re-sincroniza la clasificación/próximo rival de todos los clubes (para cron).'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', dest='workspace_slug', default='', help='Limita a un club (slug).')
        parser.add_argument(
            '--min-age-hours',
            type=float,
            default=6.0,
            help='No re-sincroniza contextos sincronizados hace menos de estas horas (por defecto 6).',
        )
        parser.add_argument('--force', action='store_true', help='Ignora el throttle y sincroniza todos.')
        parser.add_argument(
            '--providers',
            default='universo_rfaf,lapreferente',
            help='Providers a refrescar, separados por comas (por defecto Universo + La Preferente).',
        )
        parser.add_argument('--dry-run', action='store_true', help='Muestra qué se sincronizaría sin hacerlo.')

    def handle(self, *args, **options):
        slug = str(options.get('workspace_slug') or '').strip()
        min_age_hours = float(options.get('min_age_hours') or 0)
        force = bool(options.get('force'))
        dry_run = bool(options.get('dry_run'))
        providers = {
            token.strip().lower()
            for token in str(options.get('providers') or '').split(',')
            if token.strip()
        }

        qs = (
            WorkspaceCompetitionContext.objects
            .filter(provider__in=providers, workspace__kind=Workspace.KIND_CLUB, workspace__is_active=True)
            .select_related('workspace', 'team')
            .order_by('workspace__name', 'id')
        )
        if slug:
            qs = qs.filter(workspace__slug=slug)

        contexts = list(qs)
        if not contexts:
            self.stdout.write(self.style.WARNING('No hay contextos competitivos de club que refrescar.'))
            return

        now = timezone.now()
        refreshed = skipped = failed = 0
        for context in contexts:
            workspace = context.workspace
            primary_team = context.team or getattr(workspace, 'primary_team', None)
            label = f'{getattr(workspace, "name", "?")} · {getattr(primary_team, "name", "?")} · ctx#{context.id}'

            if not primary_team:
                skipped += 1
                self.stdout.write(f'  [skip] {label}: sin equipo vinculado.')
                continue

            if not force and min_age_hours > 0 and context.last_sync_at:
                age_hours = (now - context.last_sync_at).total_seconds() / 3600.0
                if age_hours < min_age_hours:
                    skipped += 1
                    self.stdout.write(f'  [fresh] {label}: sincronizado hace {age_hours:.1f}h, se omite.')
                    continue

            if dry_run:
                refreshed += 1
                self.stdout.write(self.style.NOTICE(f'  [dry] {label}: se sincronizaría.'))
                continue

            try:
                synced, message = sync_workspace_competition_context(workspace, primary_team=primary_team)
            except Exception as exc:  # noqa: BLE001 — un club no debe tumbar el refresco del resto.
                failed += 1
                self.stdout.write(self.style.ERROR(f'  [err] {label}: {exc}'))
                continue

            status = getattr(synced, 'sync_status', '')
            if status == WorkspaceCompetitionContext.STATUS_ERROR:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  [err] {label}: {message or synced.sync_error}'))
            else:
                refreshed += 1
                self.stdout.write(self.style.SUCCESS(f'  [ok] {label}: {status}.'))

        summary = f'Refrescados: {refreshed} · omitidos: {skipped} · fallidos: {failed} (de {len(contexts)}).'
        self.stdout.write((self.style.SUCCESS if not failed else self.style.WARNING)(summary))
