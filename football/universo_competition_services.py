from .event_taxonomy import normalize_label
from .query_helpers import _normalize_team_lookup_key
from .team_media_services import (
    absolute_universo_url,
    build_team_crest_lookup,
    sanitize_universo_external_image,
)


def universo_category_hints(category: str) -> list[str]:
    raw = normalize_label(category or '')
    if not raw:
        return []
    mapping = [
        ('prebenjamin', 'prebenjam'),
        ('pre-benjamin', 'prebenjam'),
        ('benjamin', 'benjam'),
        ('alevin', 'alevin'),
        ('infantil', 'infantil'),
        ('cadete', 'cadete'),
        ('juvenil', 'juvenil'),
        ('senior', 'senior'),
        ('sénior', 'senior'),
    ]
    hints = []
    for needle, token in mapping:
        if needle in raw and token not in hints:
            hints.append(token)
    if not hints:
        first = raw.split(' ', 1)[0].strip()
        if first and len(first) >= 4:
            hints.append(first)
    return hints


def universo_payload_matches_category(live_payload: dict, category: str) -> bool:
    hints = universo_category_hints(category)
    if not hints:
        return True
    hints = [hint for hint in hints if hint != 'senior']
    if not hints:
        return True
    if not isinstance(live_payload, dict):
        return False
    candidates = []
    for key in (
        'competicion',
        'competition',
        'competition_name',
        'NombreCategoria',
        'categoria',
        'category',
        'tipo_competicion',
        'tipoCompeticion',
        'grupo',
        'group',
        'group_name',
    ):
        value = live_payload.get(key)
        if value:
            candidates.append(str(value))
    combined = normalize_label(' '.join(candidates))
    if not combined:
        return True
    return any(hint in combined for hint in hints)


def safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def serialize_universo_live_classification(payload):
    if not isinstance(payload, dict):
        return []
    rows = payload.get('clasificacion') or payload.get('rows')
    if not isinstance(rows, list):
        return []
    crest_lookup = build_team_crest_lookup()
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        team = str(
            row.get('nombre')
            or row.get('Nombre_equipo')
            or row.get('equipo')
            or row.get('team')
            or ''
        ).strip()
        if not team:
            continue
        team_code = str(
            row.get('codequipo') or row.get('CodEquipo') or row.get('team_code') or ''
        ).strip()
        crest_url = str(
            row.get('url_img')
            or row.get('url_escudo')
            or row.get('escudo')
            or row.get('crest_url')
            or ''
        ).strip()
        crest_url = sanitize_universo_external_image(absolute_universo_url(crest_url)) if crest_url else ''
        gf = safe_int(
            row.get('gf')
            or row.get('goles_favor')
            or row.get('goals_for')
            or row.get('favor')
            or row.get('golesFavor')
        )
        ga = safe_int(
            row.get('gc')
            or row.get('goles_contra')
            or row.get('goals_against')
            or row.get('contra')
            or row.get('golesContra')
        )
        gd = (
            row.get('dg')
            or row.get('dif')
            or row.get('goal_difference')
            or row.get('diferencia')
            or row.get('diferencia_goles')
        )
        if gd in (None, ''):
            gd = gf - ga
        normalized.append(
            {
                'rank': safe_int(
                    row.get('posicion') or row.get('pos') or row.get('position') or row.get('rank'),
                    default=0,
                ),
                'team': team.strip().upper(),
                'full_name': team,
                'crest_url': crest_url or crest_lookup.get(_normalize_team_lookup_key(team)) or '',
                'team_code': team_code,
                'played': safe_int(row.get('pj') or row.get('jugados') or row.get('played')),
                'wins': safe_int(row.get('pg') or row.get('ganados') or row.get('wins')),
                'draws': safe_int(row.get('pe') or row.get('empatados') or row.get('draws')),
                'losses': safe_int(row.get('pp') or row.get('perdidos') or row.get('losses')),
                'goals_for': gf,
                'goals_against': ga,
                'goal_difference': safe_int(gd),
                'points': safe_int(row.get('puntos') or row.get('pts') or row.get('points')),
            }
        )
    return sorted(normalized, key=lambda x: (x['rank'] <= 0, x['rank'], -x['points'], x['full_name']))
