from django.core.cache import cache

from .models import Match

DASHBOARD_CACHE_KEY_PREFIX = "football:dashboard_payload"
PLAYER_DASHBOARD_CACHE_KEY_PREFIX = "football:player_dashboard"


def dashboard_cache_key(team_id):
    return f'{DASHBOARD_CACHE_KEY_PREFIX}:{team_id}'


def team_metrics_cache_key(team_id):
    return f'football:team_metrics:{team_id}'


def player_metrics_cache_key(team_id):
    return f'football:player_metrics:{team_id}'


def _metrics_version(team_id):
    return cache.get(f'football:metrics_ver:{team_id}') or 0


def bump_metrics_version(team_id):
    """Invalida las métricas de equipo/jugador subiendo su versión (O(1), inmune a scope/temporada)."""
    key = f'football:metrics_ver:{team_id}'
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, None)


def team_metrics_cache_key_scoped(team_id, scope, season_id=None):
    return f'{team_metrics_cache_key(team_id)}:v{_metrics_version(team_id)}:{scope}:s{int(season_id or 0)}'


def player_metrics_cache_key_scoped(team_id, scope, season_id=None):
    return f'{player_metrics_cache_key(team_id)}:v{_metrics_version(team_id)}:{scope}:s{int(season_id or 0)}'


def player_dashboard_cache_key(team_id):
    return f'{PLAYER_DASHBOARD_CACHE_KEY_PREFIX}:{team_id}'


def player_dashboard_cache_key_scoped(team_id, season_id=None):
    base = player_dashboard_cache_key(team_id)
    if season_id:
        return f'{base}:s{int(season_id)}'
    return base


def invalidate_team_dashboard_caches(primary_team):
    if not primary_team or not getattr(primary_team, 'id', None):
        return
    base_player_key_legacy = player_dashboard_cache_key(primary_team.id)
    season_id = None
    try:
        season_id = int(getattr(getattr(primary_team, 'group', None), 'season_id', 0) or 0) or None
    except Exception:
        season_id = None
    base_player_key = player_dashboard_cache_key_scoped(primary_team.id, season_id=season_id)
    scoped_player_keys = []
    for base in {base_player_key_legacy, base_player_key}:
        scoped_player_keys.extend(
            [
                f'{base}:{Match.CONTEXT_LEAGUE}',
                f'{base}:{Match.CONTEXT_TOURNAMENT}',
                f'{base}:{Match.CONTEXT_FRIENDLY}',
                f'{base}:all',
            ]
        )
    cache.delete_many(
        [
            dashboard_cache_key(primary_team.id),
            base_player_key_legacy,
            base_player_key,
            *scoped_player_keys,
        ]
    )
    # Métricas de equipo/jugador: clave versionada (equipo:vN:scope:sSeason). El delete directo
    # no casaba con la clave real (le faltaban scope/temporada); invalidamos subiendo la versión.
    bump_metrics_version(primary_team.id)
