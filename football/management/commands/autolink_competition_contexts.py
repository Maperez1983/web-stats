"""
Engancha cada equipo dado de alta a su liga (contexto competitivo), en bloque.

La configuración liga<->equipo vive por equipo (WorkspaceCompetitionContext) y normalmente se
rellena en el onboarding. Este comando replica esa autodetección para TODOS los equipos de club de
una vez, para no tener que entrar equipo por equipo:

- Universo: intenta vincular grupo/equipo por nombre (reutiliza el mismo binding del onboarding y del
  sync). Solo ata cuando hay una coincidencia clara; si hay varias, lo deja para revisión manual.
- La Preferente: detecta la URL del equipo por nombre (find_preferente_team_url, que valida la ficha).

Es CONSERVADOR: por defecto solo informa (no escribe). Con --commit aplica los cambios; con --sync
lanza además la sincronización para que la clasificación quede lista. Idempotente: reejecutarlo no
rompe lo ya vinculado.

Nota: debe correr donde están los datos reales (producción). En local solo verás los workspaces demo.
"""

from django.core.management.base import BaseCommand

from football.models import Team, Workspace, WorkspaceCompetitionContext, WorkspaceTeam
from football.workspace_competition_context_services import bootstrap_workspace_competition_context


class Command(BaseCommand):
    help = 'Vincula en bloque cada equipo de club a su liga (Universo / La Preferente).'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', dest='workspace_slug', default='', help='Limita a un club (slug).')
        parser.add_argument('--commit', action='store_true', help='Aplica los cambios (por defecto solo informa).')
        parser.add_argument('--sync', action='store_true', help='Sincroniza tras vincular (requiere --commit).')
        parser.add_argument(
            '--prefer',
            choices=['universo', 'lapreferente'],
            default='universo',
            help='Proveedor a intentar primero cuando el equipo no tiene ninguno (por defecto universo).',
        )
        parser.add_argument(
            '--only-preferente',
            action='store_true',
            help='Solo intenta La Preferente (no toca Universo). Pensado para el pase de senior desde IP residencial.',
        )
        parser.add_argument(
            '--senior-only',
            action='store_true',
            help='Limita a equipos senior (category contiene "senior", o el equipo principal del club sin categoría).',
        )

    def handle(self, *args, **options):
        slug = str(options.get('workspace_slug') or '').strip()
        commit = bool(options.get('commit'))
        do_sync = bool(options.get('sync')) and commit
        prefer = str(options.get('prefer') or 'universo')
        only_preferente = bool(options.get('only_preferente'))
        senior_only = bool(options.get('senior_only'))
        if only_preferente:
            prefer = 'lapreferente'

        workspaces = Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).order_by('name', 'id')
        if slug:
            workspaces = workspaces.filter(slug=slug)
        workspaces = list(workspaces)
        if not workspaces:
            self.stdout.write(self.style.WARNING('No hay clubes activos.'))
            return

        counters = {'ready': 0, 'linked': 0, 'ambiguous': 0, 'unmatched': 0, 'synced': 0, 'failed': 0}
        for workspace in workspaces:
            team_ids = list(
                WorkspaceTeam.objects.filter(workspace=workspace).values_list('team_id', flat=True)
            )
            primary_id = int(getattr(workspace, 'primary_team_id', 0) or 0)
            if primary_id and primary_id not in team_ids:
                team_ids.append(primary_id)
            teams = list(Team.objects.filter(id__in=team_ids).order_by('name', 'id')) if team_ids else []
            if senior_only:
                teams = [t for t in teams if self._is_senior_team(t, primary_id)]
            if not teams:
                continue
            self.stdout.write(f'{workspace.name} ({workspace.slug})')
            for team in teams:
                self._process_team(
                    workspace, team, commit=commit, do_sync=do_sync, prefer=prefer,
                    only_preferente=only_preferente, counters=counters,
                )

        mode = 'APLICADO' if commit else 'SIMULACIÓN (usa --commit para aplicar)'
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'[{mode}] listos={counters["ready"]} vinculados={counters["linked"]} '
                f'ambiguos={counters["ambiguous"]} sin_liga={counters["unmatched"]} '
                f'sincronizados={counters["synced"]} fallidos={counters["failed"]}'
            )
        )
        if counters['ambiguous']:
            self.stdout.write(
                self.style.WARNING(
                    'Los "ambiguos" tienen varias ligas candidatas: configúralos a mano en /onboarding/.'
                )
            )

    @staticmethod
    def _is_senior_team(team, primary_id):
        category = str(getattr(team, 'category', '') or '').strip().lower()
        if 'senior' in category:
            return True
        # El equipo principal del club, si no tiene categoría marcada, se asume senior.
        return not category and int(getattr(team, 'id', 0) or 0) == int(primary_id or 0)

    def _process_team(self, workspace, team, *, commit, do_sync, prefer, counters, only_preferente=False):
        label = f'  {team.name}'
        context = None
        if commit:
            context = bootstrap_workspace_competition_context(workspace, primary_team=team)
        else:
            context = (
                WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=team).first()
            )
        provider = str(getattr(context, 'provider', '') or '').strip().lower()

        # ¿Ya está enganchado?
        already_universo = bool(
            provider == WorkspaceCompetitionContext.PROVIDER_UNIVERSO
            and str(getattr(context, 'external_group_key', '') or '').strip()
        )
        already_preferente = bool(
            provider == WorkspaceCompetitionContext.PROVIDER_PREFERENTE
            and str(getattr(team, 'preferente_url', '') or '').strip()
        )
        if already_universo or already_preferente:
            counters['ready'] += 1
            self.stdout.write(self.style.SUCCESS(f'{label}: ya enganchado ({provider}).'))
            if do_sync:
                self._sync(workspace, team, counters)
            return

        # Intento de vinculación, respetando el proveedor si ya viene fijado.
        universo = WorkspaceCompetitionContext.PROVIDER_UNIVERSO
        preferente = WorkspaceCompetitionContext.PROVIDER_PREFERENTE
        prefer_provider = preferente if prefer == 'lapreferente' else universo
        if only_preferente:
            # Pase de senior desde IP residencial: no tocamos Universo.
            order = [preferente]
        elif provider in {universo, preferente}:
            order = [provider]
        elif prefer_provider == preferente:
            order = [preferente, universo]
        else:
            order = [universo, preferente]

        for candidate_provider in order:
            if candidate_provider == WorkspaceCompetitionContext.PROVIDER_UNIVERSO:
                if self._try_universo(workspace, team, context, commit=commit, label=label, counters=counters):
                    if do_sync:
                        self._sync(workspace, team, counters)
                    return
            elif candidate_provider == WorkspaceCompetitionContext.PROVIDER_PREFERENTE:
                if self._try_preferente(workspace, team, context, commit=commit, label=label, counters=counters):
                    if do_sync:
                        self._sync(workspace, team, counters)
                    return

        counters['unmatched'] += 1
        self.stdout.write(self.style.WARNING(f'{label}: sin liga detectada (revisar a mano).'))

    def _try_universo(self, workspace, team, context, *, commit, label, counters):
        try:
            from football.views import _search_universo_competition_candidates

            candidates = _search_universo_competition_candidates(team_query=team.name) or []
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f'{label}: error buscando en Universo: {exc}'))
            return False
        if len(candidates) > 1:
            counters['ambiguous'] += 1
            names = ', '.join(str(c.get('team_name') or '?') for c in candidates[:4])
            self.stdout.write(self.style.WARNING(f'{label}: Universo ambiguo ({len(candidates)}): {names}…'))
            return True  # tratado (queda para revisión manual), no seguir con Preferente
        if len(candidates) == 1:
            item = candidates[0]
            group_key = str(item.get('external_group_key') or '').strip()
            team_key = str(item.get('external_team_key') or '').strip()
            if not group_key:
                return False
            if commit:
                bootstrap_workspace_competition_context(
                    workspace,
                    primary_team=team,
                    provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
                    external_competition_key=str(item.get('external_competition_key') or ''),
                    external_group_key=group_key,
                    external_team_key=team_key,
                    external_team_name=str(item.get('team_name') or team.name),
                    auto_sync_enabled=True,
                )
            counters['linked'] += 1
            self.stdout.write(
                self.style.SUCCESS(f'{label}: {"vinculado" if commit else "vinculable"} a Universo ({item.get("team_name")}).')
            )
            return True
        return False

    def _try_preferente(self, workspace, team, context, *, commit, label, counters):
        try:
            from football.services import find_preferente_team_url

            url = str(find_preferente_team_url(team.name) or '').strip()
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f'{label}: error buscando en La Preferente: {exc}'))
            return False
        if not url:
            return False
        if commit:
            if str(getattr(team, 'preferente_url', '') or '').strip() != url:
                team.preferente_url = url
                team.save(update_fields=['preferente_url'])
            bootstrap_workspace_competition_context(
                workspace,
                primary_team=team,
                provider=WorkspaceCompetitionContext.PROVIDER_PREFERENTE,
                external_source_url=url,
                external_team_name=team.name,
                auto_sync_enabled=True,
            )
        counters['linked'] += 1
        self.stdout.write(self.style.SUCCESS(f'{label}: {"vinculado" if commit else "vinculable"} a La Preferente ({url}).'))
        return True

    def _sync(self, workspace, team, counters):
        from football.competition_sync import sync_workspace_competition_context

        try:
            synced, message = sync_workspace_competition_context(workspace, primary_team=team)
        except Exception as exc:  # noqa: BLE001
            counters['failed'] += 1
            self.stdout.write(self.style.ERROR(f'    sync error: {exc}'))
            return
        if getattr(synced, 'sync_status', '') == WorkspaceCompetitionContext.STATUS_ERROR:
            counters['failed'] += 1
            self.stdout.write(self.style.ERROR(f'    sync: {message or synced.sync_error}'))
        else:
            counters['synced'] += 1
            self.stdout.write(f'    sync: {getattr(synced, "sync_status", "")}.')
