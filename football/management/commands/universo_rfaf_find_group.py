import os
import re
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


def _norm(text: str) -> str:
    raw = str(text or '').strip().lower()
    # Quita acentos/diacríticos (Benagalbón -> benagalbon).
    try:
        raw = unicodedata.normalize('NFD', raw)
        raw = ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn')
    except Exception:
        pass
    return re.sub(r'[^a-z0-9]+', '', raw)


class Command(BaseCommand):
    help = (
        'Busca el group-id (Universo RFAF) para un equipo/competición.\n'
        'Estrategia: lista temporadas/delegaciones/competiciones/grupos y prueba `get-classification` '
        'hasta encontrar un grupo que contenga al equipo.\n'
        'Útil para configurar `Group.external_id` y poder sincronizar rivales.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--team-id', type=int, default=0, help='ID del equipo en nuestra BD (football.Team).')
        parser.add_argument('--team-code', default='', help='Código de equipo en Universo (Team.external_id).')
        parser.add_argument('--team-name', default='', help='Nombre del equipo (fallback si no hay código).')
        parser.add_argument(
            '--no-auto-filters',
            action='store_true',
            help='No autocompleta filtros (season/competition/group) desde Team.group. Útil para buscar en toda la delegación.',
        )
        parser.add_argument(
            '--list-matches',
            action='store_true',
            help='En vez de parar en el primer match, lista todos los grupos donde aparece el equipo (por nombre/código).',
        )
        parser.add_argument('--season-contains', default='', help='Filtra temporada (texto contenido). Ej: 2025/2026')
        parser.add_argument('--delegation-contains', default='', help='Filtra delegación (texto contenido). Ej: Málaga')
        parser.add_argument('--competition-contains', default='', help='Filtra competición (texto contenido).')
        parser.add_argument('--group-contains', default='', help='Filtra grupo (texto contenido). Ej: Grupo 2')
        parser.add_argument('--limit-groups', type=int, default=120, help='Límite de grupos a probar (guardrail).')

    def handle(self, *args, **options):
        from football.models import Team
        from football.universo_client import (
            fetch_universo_live_classification,
            fetch_universo_live_competitions,
            fetch_universo_live_delegations,
            fetch_universo_live_groups,
            fetch_universo_live_seasons,
            load_universo_access_token,
        )

        team_id = int(options.get('team_id') or 0)
        team_code = str(options.get('team_code') or '').strip()
        team_name = str(options.get('team_name') or '').strip()
        no_auto_filters = bool(options.get('no_auto_filters'))
        list_matches = bool(options.get('list_matches'))
        season_contains = str(options.get('season_contains') or '').strip()
        delegation_contains = str(options.get('delegation_contains') or '').strip()
        competition_contains = str(options.get('competition_contains') or '').strip()
        group_contains = str(options.get('group_contains') or '').strip()
        limit_groups = max(1, int(options.get('limit_groups') or 120))

        if team_id:
            team = Team.objects.select_related('group', 'group__season', 'group__season__competition').filter(id=team_id).first()
            if not team:
                raise CommandError(f'No existe Team con id={team_id}')
            if not team_code:
                team_code = str(getattr(team, 'external_id', '') or '').strip()
            if not team_name:
                team_name = str(getattr(team, 'name', '') or '').strip()
            if (not no_auto_filters) and getattr(team, 'group', None):
                if not group_contains:
                    group_contains = str(getattr(team.group, 'name', '') or '').strip()
                if not competition_contains and getattr(team.group, 'season', None):
                    competition_contains = str(getattr(team.group.season.competition, 'name', '') or '').strip()
                if not season_contains and getattr(team.group, 'season', None):
                    season_contains = str(getattr(team.group.season, 'name', '') or '').strip()

        if not team_code and not team_name:
            raise CommandError('Indica --team-id o bien --team-code/--team-name.')

        token = load_universo_access_token()
        if not token:
            raise CommandError('No hay sesión/token de Universo RFAF. Revisa UNIVERSO_RFAF_* en env.')

        self.stdout.write('== Universo RFAF: find group-id ==')
        self.stdout.write(f"Team code: {team_code or '(none)'}")
        self.stdout.write(f"Team name: {team_name or '(none)'}")
        if season_contains:
            self.stdout.write(f'Season filter: {season_contains}')
        if delegation_contains:
            self.stdout.write(f'Delegation filter: {delegation_contains}')
        if competition_contains:
            self.stdout.write(f'Competition filter: {competition_contains}')
        if group_contains:
            self.stdout.write(f'Group filter: {group_contains}')

        seasons = fetch_universo_live_seasons() or []
        if not seasons:
            raise CommandError('No se pudieron listar temporadas desde Universo.')

        def _season_name(row):
            return str(row.get('nombre') or row.get('temporada') or row.get('name') or '').strip()

        if season_contains:
            target = season_contains.lower()
            seasons = [s for s in seasons if target in _season_name(s).lower()]
        if not seasons:
            raise CommandError('No hay temporadas que coincidan con el filtro.')
        # Heurística: usa la primera del listado filtrado.
        season = seasons[0]
        season_id = str(season.get('id') or season.get('codigo') or season.get('cod_temporada') or season.get('season_id') or '').strip()
        season_label = _season_name(season) or season_id
        if not season_id:
            raise CommandError('No se pudo resolver el id de temporada.')
        self.stdout.write(f'Using season: {season_label} (id={season_id})')

        delegations = fetch_universo_live_delegations() or []
        if not delegations:
            raise CommandError('No se pudieron listar delegaciones desde Universo.')

        def _deleg_name(row):
            return str(row.get('nombre') or row.get('delegacion') or row.get('name') or '').strip()

        if delegation_contains:
            target = delegation_contains.lower()
            delegations = [d for d in delegations if target in _deleg_name(d).lower()]
        if not delegations:
            raise CommandError('No hay delegaciones que coincidan con el filtro.')

        normalized_team_name = _norm(team_name) if team_name else ''
        normalized_competition_filter = _norm(competition_contains) if competition_contains else ''
        normalized_group_filter = _norm(group_contains) if group_contains else ''

        tested = 0
        candidates_seen = 0
        started = timezone.now()
        matches = []

        for delegation in delegations:
            delegation_id = str(delegation.get('id') or delegation.get('codigo') or delegation.get('cod_delegacion') or delegation.get('delegation_id') or '').strip()
            if not delegation_id:
                continue
            delegation_label = _deleg_name(delegation) or delegation_id

            competitions = fetch_universo_live_competitions(delegation_id, season_id) or []
            if normalized_competition_filter:
                competitions = [
                    c for c in competitions
                    if normalized_competition_filter in _norm(c.get('nombre') or c.get('competicion') or c.get('name') or '')
                ]
            if not competitions:
                continue

            for comp in competitions:
                comp_id = str(comp.get('id') or comp.get('codigo') or comp.get('cod_competicion') or comp.get('competition_id') or '').strip()
                if not comp_id:
                    continue
                comp_label = str(comp.get('nombre') or comp.get('competicion') or comp.get('name') or '').strip() or comp_id

                groups = fetch_universo_live_groups(comp_id) or []
                if normalized_group_filter:
                    groups = [
                        g for g in groups
                        if normalized_group_filter in _norm(g.get('nombre') or g.get('grupo') or g.get('name') or '')
                    ]
                if not groups:
                    continue

                for group in groups:
                    group_id = str(group.get('id') or group.get('codigo') or group.get('cod_grupo') or group.get('group_id') or '').strip()
                    if not group_id or not group_id.isdigit():
                        continue
                    candidates_seen += 1
                    if candidates_seen > limit_groups:
                        raise CommandError(f'Se alcanzó el límite de grupos ({limit_groups}). Ajusta filtros o sube --limit-groups.')

                    payload = fetch_universo_live_classification(group_id)
                    rows = payload.get('clasificacion') if isinstance(payload, dict) else None
                    if not isinstance(rows, list) or not rows:
                        continue
                    tested += 1

                    codes = set()
                    names = set()
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        codes.add(str(row.get('codequipo') or row.get('cod_equipo') or '').strip())
                        names.add(_norm(row.get('nombre') or row.get('team') or row.get('equipo') or ''))

                    found = False
                    if team_code and team_code in codes:
                        found = True
                    elif normalized_team_name:
                        if normalized_team_name in names:
                            found = True
                        else:
                            # Match tolerante (prefijos/sufijos tipo "C.D.", acentos, etc.)
                            for candidate in names:
                                if not candidate:
                                    continue
                                if normalized_team_name in candidate or candidate in normalized_team_name:
                                    found = True
                                    break

                    if found:
                        group_label = str(group.get('nombre') or group.get('grupo') or group.get('name') or '').strip() or f'group {group_id}'
                        matches.append(
                            {
                                'delegation': delegation_label,
                                'delegation_id': delegation_id,
                                'competition': comp_label,
                                'competition_id': comp_id,
                                'group': group_label,
                                'group_id': group_id,
                            }
                        )
                        if not list_matches:
                            self.stdout.write(self.style.SUCCESS('MATCH'))
                            self.stdout.write(f'- delegation: {delegation_label} (id={delegation_id})')
                            self.stdout.write(f'- competition: {comp_label} (id={comp_id})')
                            self.stdout.write(f'- group: {group_label} (id_group={group_id})')
                            self.stdout.write(f'- tested_groups: {tested} / candidates_seen: {candidates_seen}')
                            elapsed = (timezone.now() - started).total_seconds()
                            self.stdout.write(f'- elapsed_s: {elapsed:.1f}')
                            self.stdout.write('')
                            self.stdout.write('Sugerencia: guarda este id en `Group.external_id` para ese equipo/categoría.')
                            return

        elapsed = (timezone.now() - started).total_seconds()
        if matches:
            self.stdout.write(self.style.SUCCESS(f'MATCHES ({len(matches)}):'))
            for item in matches[:50]:
                self.stdout.write(f"- {item['competition']} · {item['group']} · id_group={item['group_id']}")
            self.stdout.write(f'- tested_groups: {tested} / candidates_seen: {candidates_seen}')
            self.stdout.write(f'- elapsed_s: {elapsed:.1f}')
            return
        raise CommandError(f'No se encontró group-id (probados {tested}, candidatos {candidates_seen}) en {elapsed:.1f}s. Ajusta filtros.')
