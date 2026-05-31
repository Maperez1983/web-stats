import json

from django.core.management.base import BaseCommand

from football.models import Workspace
from football.season_history_services import backfill_workspace_club_seasons, season_architecture_audit


class Command(BaseCommand):
    help = 'Audita la distribución de datos por temporada interna de club.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', dest='workspace_slug', default='', help='Slug del club/workspace a auditar.')
        parser.add_argument('--json', action='store_true', dest='as_json', help='Devuelve la auditoría completa en JSON.')
        parser.add_argument('--backfill', action='store_true', help='Asigna club_season a registros inferibles por fecha.')

    def handle(self, *args, **options):
        slug = str(options.get('workspace_slug') or '').strip()
        qs = Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).order_by('name', 'id')
        if slug:
            qs = qs.filter(slug=slug)
        workspaces = list(qs)
        if not workspaces:
            self.stdout.write(self.style.WARNING('No se encontraron clubes activos para auditar.'))
            return

        if options.get('backfill'):
            reports = [backfill_workspace_club_seasons(workspace, dry_run=False) for workspace in workspaces]
        else:
            reports = [season_architecture_audit(workspace) for workspace in workspaces]
        if options.get('as_json'):
            self.stdout.write(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))
            return

        for workspace, report in zip(workspaces, reports):
            self.stdout.write(f'{workspace.name} ({workspace.slug})')
            if options.get('backfill'):
                for model_key, model_report in sorted((report.get('models') or {}).items()):
                    assigned = (
                        model_report.get('assigned', 0)
                        + model_report.get('assigned_from_session', 0)
                        + model_report.get('assigned_from_date', 0)
                    )
                    self.stdout.write(
                        '  '
                        f"{model_key}: asignados={assigned} "
                        f"ya_asignados={model_report.get('already_assigned', 0)} "
                        f"sin_fecha={model_report.get('without_date', 0)} "
                        f"fuera_temporada={model_report.get('outside_seasons', 0)}"
                    )
                continue
            self.stdout.write(f"  temporadas: {report.get('season_count', 0)} · activa: {report.get('active_season_id') or '-'}")
            for model_key, model_report in sorted((report.get('models') or {}).items()):
                self.stdout.write(
                    '  '
                    f"{model_key}: total={model_report.get('total', 0)} "
                    f"explicitos={model_report.get('explicit', 0)} "
                    f"sin_fecha={model_report.get('without_date', 0)} "
                    f"fuera_temporada={model_report.get('outside_seasons', 0)}"
                )
