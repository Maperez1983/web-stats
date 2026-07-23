from django.db.models import Count, Max

from .models import TeamStanding, WorkspaceCompetitionContext
from .query_helpers import _normalize_team_lookup_key
from .team_media_services import (
    absolute_universo_url,
    build_team_crest_lookup,
    resolve_team_crest_url,
    sanitize_universo_external_image,
)
from .universo_competition_services import safe_int
from .universo_snapshot_services import load_universo_snapshot
from .workspace_context import single_club_fallback_enabled


def latest_standings_group_for_team(primary_team):
    if not primary_team:
        return None
    try:
        base_qs = (
            TeamStanding.objects
            .select_related('group')
            .filter(team=primary_team)
            .order_by('-last_updated', '-played', '-id')
        )
        # Prioridad a la clasificación de la temporada a la que el equipo está asignado ahora
        # (`Team.group.season`). Sin esto, en pretemporada —con la tabla nueva aún vacía— el
        # "más reciente por last_updated" era el grupo de la campaña pasada, y la portada pintaba
        # la clasificación vieja como si fuera la actual.
        current_season_id = int(getattr(getattr(primary_team, 'group', None), 'season_id', 0) or 0)
        if current_season_id:
            in_season = base_qs.filter(group__season_id=current_season_id).first()
            if in_season:
                return in_season.group
        standing = base_qs.first()
        return standing.group if standing else None
    except Exception:
        return None


def serialize_standings(group):
    standings = TeamStanding.objects.filter(group=group)
    current_meta = standings.aggregate(total=Count('id'), latest=Max('last_updated'))

    sibling_group = (
        TeamStanding.objects.filter(
            group__season=group.season,
            group__name__iexact=group.name,
        )
        .values('group_id')
        .annotate(total=Count('id'), latest=Max('last_updated'))
        .order_by('-latest', '-total')
        .first()
    )
    if sibling_group:
        sibling_is_better = (
            current_meta['total'] == 0
            or (
                sibling_group['group_id'] != group.id
                and sibling_group['latest']
                and (
                    not current_meta['latest']
                    or sibling_group['latest'] > current_meta['latest']
                )
            )
        )
        if sibling_is_better:
            standings = TeamStanding.objects.filter(group_id=sibling_group['group_id'])

    standings = standings.order_by('position')
    crest_lookup = build_team_crest_lookup()
    return [
        {
            'rank': standing.position,
            'team': standing.team.name.strip().upper(),
            'full_name': standing.team.name.strip(),
            'crest_url': resolve_team_crest_url(
                None,
                standing.team,
                fallback_static='',
                sync=False,
            )
            or sanitize_universo_external_image(
                absolute_universo_url(
                    getattr(standing.team, 'crest_url', '')
                    or crest_lookup.get(_normalize_team_lookup_key(standing.team.name))
                    or ''
                )
            ),
            'played': standing.played,
            'wins': standing.wins,
            'draws': standing.draws,
            'losses': standing.losses,
            'goals_for': standing.goals_for,
            'goals_against': standing.goals_against,
            'goal_difference': standing.goal_difference,
            'points': standing.points,
        }
        for standing in standings
    ]


def universo_snapshot_supports_team(snapshot, primary_team):
    if not primary_team:
        return True
    if not single_club_fallback_enabled():
        return False
    if not bool(getattr(primary_team, 'is_primary', False)):
        return False
    if not isinstance(snapshot, dict):
        return False
    rows = snapshot.get('standings')
    candidate_keys = {
        _normalize_team_lookup_key(primary_team.name),
        _normalize_team_lookup_key(primary_team.display_name),
    }
    candidate_keys = {key for key in candidate_keys if key}
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_keys = {
                _normalize_team_lookup_key(row.get('team')),
                _normalize_team_lookup_key(row.get('full_name')),
            }
            row_keys = {key for key in row_keys if key}
            if candidate_keys & row_keys:
                return True
        return False
    return bool(getattr(primary_team, 'is_primary', False))


def serialize_universo_standings(snapshot):
    if not isinstance(snapshot, dict):
        return []
    rows = snapshot.get('standings')
    if not isinstance(rows, list):
        return []
    crest_lookup = build_team_crest_lookup()
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        team = str(row.get('team') or '').strip()
        if not team:
            continue
        gf = safe_int(row.get('goals_for'))
        ga = safe_int(row.get('goals_against'))
        gd = row.get('goal_difference')
        if gd in (None, ''):
            gd = gf - ga
        normalized.append(
            {
                'rank': safe_int(row.get('position'), default=0),
                'team': team,
                'full_name': str(row.get('full_name') or team).strip() or team,
                'crest_url': str(
                    row.get('crest_url')
                    or crest_lookup.get(_normalize_team_lookup_key(team))
                    or ''
                ).strip(),
                'team_code': str(row.get('team_code') or '').strip(),
                'played': safe_int(row.get('played')),
                'wins': safe_int(row.get('wins')),
                'draws': safe_int(row.get('draws')),
                'losses': safe_int(row.get('losses')),
                'goals_for': gf,
                'goals_against': ga,
                'goal_difference': safe_int(gd),
                'points': safe_int(row.get('points')),
            }
        )
    return sorted(normalized, key=lambda x: (x['rank'] <= 0, x['rank'], -x['points'], x['full_name']))


def resolve_standings_for_team(primary_team, snapshot=None, provider=None):
    if not primary_team or not getattr(primary_team, 'group', None):
        return []
    snapshot = snapshot if snapshot is not None else load_universo_snapshot()
    provider_key = str(provider or '').strip().lower()
    if provider_key == WorkspaceCompetitionContext.PROVIDER_UNIVERSO:
        if not bool(getattr(primary_team, 'is_primary', False)):
            return serialize_standings(primary_team.group)
        if universo_snapshot_supports_team(snapshot, primary_team):
            universo_rows = serialize_universo_standings(snapshot)
            if universo_rows:
                return universo_rows
        return serialize_standings(primary_team.group)

    group_for_db = latest_standings_group_for_team(primary_team) or primary_team.group
    db_rows = serialize_standings(group_for_db)
    if db_rows:
        return db_rows
    if (
        bool(getattr(primary_team, 'is_primary', False))
        and universo_snapshot_supports_team(snapshot, primary_team)
    ):
        universo_rows = serialize_universo_standings(snapshot)
        if universo_rows:
            return universo_rows
    return serialize_standings(primary_team.group)
