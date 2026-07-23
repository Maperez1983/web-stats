"""
Revincula los contextos competitivos de los clubes a la temporada de competición vigente.

Cada 1 de julio (corte configurable) arranca una temporada nueva en la federación. Los clubes
que quedaron vinculados al grupo de Universo de la campaña anterior seguirían mostrando la
clasificación y el próximo rival viejos hasta que alguien entrase a re-sincronizar a mano.

Este comando recorre los contextos Universo, detecta los que apuntan a una temporada caducada
(`binding_season_is_stale`) y fuerza una revinculación + sincronización. Pensado para lanzarse
una vez al inicio de temporada (idealmente desde un cron), o puntualmente para un club.
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from football.competition_season_services import current_season_name
from football.competition_sync import sync_workspace_competition_context
from football.models import WorkspaceCompetitionContext, WorkspaceCompetitionSnapshot
from football.universo_context_services import binding_season_is_stale


class Command(BaseCommand):
    help = 'Revincula los contextos competitivos de club a la temporada de competición vigente.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', dest='workspace_slug', default='', help='Slug del club a revincular.')
        parser.add_argument(
            '--all',
            action='store_true',
            help='Revincula también los contextos que ya parecen vigentes (fuerza refresh).',
        )
        parser.add_argument('--dry-run', action='store_true', help='Muestra qué se haría sin tocar nada.')

    def handle(self, *args, **options):
        slug = str(options.get('workspace_slug') or '').strip()
        include_all = bool(options.get('all'))
        dry_run = bool(options.get('dry_run'))

        qs = (
            WorkspaceCompetitionContext.objects
            .filter(provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
            .select_related('workspace', 'team', 'season')
            .order_by('workspace__name', 'id')
        )
        if slug:
            qs = qs.filter(workspace__slug=slug)

        target_season = current_season_name()
        self.stdout.write(f'Temporada de competición vigente: {target_season}')

        contexts = list(qs)
        if not contexts:
            self.stdout.write(self.style.WARNING('No hay contextos Universo que revincular.'))
            return

        rebound = 0
        skipped = 0
        failed = 0
        for context in contexts:
            workspace = context.workspace
            primary_team = context.team or getattr(workspace, 'primary_team', None)
            label = f'{getattr(workspace, "name", "?")} · ctx#{context.id}'

            stale = binding_season_is_stale(context, primary_team)
            if not stale and not include_all:
                skipped += 1
                self.stdout.write(f'  [ok] {label}: ya vigente, se omite.')
                continue

            if dry_run:
                rebound += 1
                self.stdout.write(self.style.NOTICE(f'  [dry] {label}: se revincularía a {target_season}.'))
                continue

            # Limpia el throttle de rebind y el snapshot caducado para forzar una resolución limpia.
            try:
                cache.delete(f'universo-context-rebind:{int(context.id)}')
            except Exception:
                pass
            WorkspaceCompetitionSnapshot.objects.filter(context=context).delete()
            context.sync_status = WorkspaceCompetitionContext.STATUS_PENDING
            context.save(update_fields=['sync_status', 'updated_at'])

            try:
                _, message = sync_workspace_competition_context(workspace, primary_team=primary_team)
            except Exception as exc:  # noqa: BLE001 — el comando debe seguir con el resto de clubes.
                failed += 1
                self.stdout.write(self.style.ERROR(f'  [err] {label}: {exc}'))
                continue

            context.refresh_from_db()
            status = context.sync_status
            if status == WorkspaceCompetitionContext.STATUS_ERROR:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  [err] {label}: {message or context.sync_error}'))
            else:
                rebound += 1
                self.stdout.write(self.style.SUCCESS(f'  [rebound] {label}: {status} ({message or "ok"}).'))

        summary = f'Revinculados: {rebound} · omitidos: {skipped} · fallidos: {failed}'
        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(summary))
