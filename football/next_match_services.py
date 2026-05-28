import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .match_payload_services import normalize_next_match_payload, parse_payload_date, payload_opponent_name
from .models import Team, WorkspaceCompetitionContext
from .query_helpers import _normalize_team_lookup_key, get_current_convocation_record
from .team_media_services import (
    absolute_universo_url,
    build_universo_capture_team_lookup,
    resolve_team_crest_url,
    sanitize_universo_external_image,
)
from .universo_client import fetch_universo_live_results
from .universo_context_services import context_team_lookup_keys
from .universo_group_services import expand_team_lookup_variants
from .universo_snapshot_services import load_universo_snapshot
from .workspace_context import single_club_fallback_enabled


def _env_path(var_name: str, default_path: Path) -> Path:
    raw = str(os.getenv(var_name, '') or '').strip()
    if raw:
        try:
            return Path(raw).expanduser()
        except Exception:
            return default_path
    return default_path


NEXT_MATCH_CACHE = _env_path(
    'NEXT_MATCH_CACHE_PATH',
    Path(settings.BASE_DIR) / 'data' / 'input' / 'rfaf-next-match.json',
)


def build_universo_standings_lookup(snapshot):
    lookup = {}
    if not isinstance(snapshot, dict):
        return lookup
    for row in snapshot.get('standings') or []:
        if not isinstance(row, dict):
            continue
        team_name = str(row.get('team') or row.get('full_name') or '').strip()
        key = _normalize_team_lookup_key(team_name)
        if not key:
            continue
        lookup[key] = {
            'full_name': str(row.get('full_name') or team_name).strip() or team_name,
            'crest_url': str(row.get('crest_url') or '').strip(),
            'team_code': str(row.get('team_code') or '').strip(),
        }
    return lookup


def resolve_rival_identity(rival_name, preferred_opponent=None):
    rival_name = str(rival_name or '').strip() or 'Rival por confirmar'
    rival_full_name = rival_name
    rival_crest_url = ''
    rival_key = _normalize_team_lookup_key(rival_name)
    known_team = (
        Team.objects
        .filter(Q(name__iexact=rival_name) | Q(short_name__iexact=rival_name) | Q(external_id__iexact=rival_name))
        .order_by('-is_primary', 'name')
        .first()
    )
    if known_team:
        rival_full_name = known_team.name
        rival_crest_url = resolve_team_crest_url(None, known_team, fallback_static='', sync=False)

    if isinstance(preferred_opponent, dict):
        preferred_name = str(preferred_opponent.get('name') or '').strip()
        preferred_full_name = str(preferred_opponent.get('full_name') or '').strip()
        preferred_key = _normalize_team_lookup_key(preferred_name or preferred_full_name)
        if preferred_key and rival_key and (
            preferred_key == rival_key
            or preferred_key in rival_key
            or rival_key in preferred_key
        ):
            rival_full_name = preferred_full_name or preferred_name or rival_full_name
            rival_crest_url = str(preferred_opponent.get('crest_url') or '').strip()

    standings_lookup = build_universo_standings_lookup(load_universo_snapshot())
    capture_lookup = build_universo_capture_team_lookup()

    best_meta = {}
    candidates = [standings_lookup.get(rival_key, {}), capture_lookup.get(rival_key, {})]
    for source in (standings_lookup, capture_lookup):
        if best_meta.get('full_name') and best_meta.get('crest_url'):
            break
        for key, meta in source.items():
            if not key or not rival_key:
                continue
            if rival_key in key or key in rival_key:
                if len(str(meta.get('full_name') or '')) > len(str(best_meta.get('full_name') or '')):
                    best_meta['full_name'] = str(meta.get('full_name') or '').strip()
                if meta.get('crest_url') and not best_meta.get('crest_url'):
                    best_meta['crest_url'] = str(meta.get('crest_url') or '').strip()
    for meta in candidates:
        if not isinstance(meta, dict):
            continue
        if len(str(meta.get('full_name') or '')) > len(str(best_meta.get('full_name') or '')):
            best_meta['full_name'] = str(meta.get('full_name') or '').strip()
        if meta.get('crest_url') and not best_meta.get('crest_url'):
            best_meta['crest_url'] = str(meta.get('crest_url') or '').strip()

    rival_full_name = best_meta.get('full_name') or rival_full_name
    rival_crest_url = best_meta.get('crest_url') or rival_crest_url
    rival_crest_url = sanitize_universo_external_image(absolute_universo_url(rival_crest_url))
    return rival_full_name, rival_crest_url


def build_next_match_from_convocation(primary_team):
    record = get_current_convocation_record(primary_team)
    if not record:
        return None
    today = timezone.localdate()
    match_date = record.match_date
    if not match_date and record.match and getattr(record.match, 'date', None):
        match_date = record.match.date
    if not match_date:
        return None
    if match_date < today:
        return None

    opponent_name = (record.opponent_name or '').strip()
    round_label = (record.round or '').strip()
    location_label = (record.location or '').strip()
    date_iso = match_date.isoformat() if match_date else None
    time_label = record.match_time.strftime('%H:%M') if record.match_time else ''

    if not any([opponent_name, round_label, date_iso, time_label, location_label]):
        return None

    home_flag = None
    match = record.match
    if match and primary_team:
        if match.home_team_id == primary_team.id:
            home_flag = True
        elif match.away_team_id == primary_team.id:
            home_flag = False

    rival_full_name, rival_crest_url = resolve_rival_identity(opponent_name or 'Rival por confirmar')

    payload = {
        'round': round_label or 'Jornada por confirmar',
        'date': date_iso,
        'time': time_label,
        'location': location_label or 'Campo por confirmar',
        'opponent': {
            'name': opponent_name or rival_full_name or 'Rival por confirmar',
            'full_name': rival_full_name or opponent_name or 'Rival por confirmar',
            'crest_url': absolute_universo_url(rival_crest_url),
            'team_code': '',
        },
        'home': home_flag if home_flag is not None else True,
        'status': 'next',
        'source': 'convocation-manual',
    }
    return normalize_next_match_payload(payload)


def find_universo_next_match_for_context(context, primary_team):
    if (
        not context
        or str(getattr(context, 'provider', '') or '').strip()
        != WorkspaceCompetitionContext.PROVIDER_UNIVERSO
    ):
        return {}
    group_key = str(getattr(context, 'external_group_key', '') or '').strip()
    if not group_key:
        group_key = str(getattr(getattr(primary_team, 'group', None), 'external_id', '') or '').strip()
    if not group_key:
        return {}
    team_keys = context_team_lookup_keys(context, primary_team)
    if not team_keys:
        return {}

    today = timezone.localdate()
    current_payload = fetch_universo_live_results(group_key)
    if not current_payload:
        return {}
    rounds = _round_ids_to_check(current_payload)
    for round_id in rounds:
        current_round = str(current_payload.get('jornada') or '').strip()
        payload = (
            current_payload
            if round_id == current_round
            else fetch_universo_live_results(group_key, round_id)
        )
        if not payload:
            continue
        fallback_date = str(payload.get('fecha_jornada') or '').strip()
        fallback_round = str(payload.get('nombre_jornada') or payload.get('jornada') or round_id).strip()
        for row in payload.get('partidos') or []:
            if not isinstance(row, dict):
                continue
            candidate = _payload_from_universo_result_row(
                row,
                team_keys=team_keys,
                fallback_date=fallback_date,
                fallback_round=fallback_round,
            )
            if not candidate:
                continue
            payload_date = parse_payload_date(candidate.get('date'))
            if payload_date and payload_date >= today:
                return candidate
    return {}


def _round_ids_to_check(current_payload):
    rounds = []
    current_round = str(current_payload.get('jornada') or '').strip()
    if current_round:
        rounds.append(current_round)
    for bucket in current_payload.get('listado_jornadas') or []:
        if not isinstance(bucket, dict):
            continue
        for row in bucket.get('jornadas') or []:
            if not isinstance(row, dict):
                continue
            round_id = str(row.get('codjornada') or '').strip()
            if round_id and round_id not in rounds:
                rounds.append(round_id)

    numeric_rounds = [rid for rid in rounds if str(rid).isdigit()]
    if numeric_rounds:
        ordered_unique = sorted({rid for rid in numeric_rounds}, key=lambda value: int(value))
        start_index = 0
        if current_round.isdigit() and current_round in ordered_unique:
            start_index = ordered_unique.index(current_round)
        return ordered_unique[start_index:start_index + 6]
    return rounds[:6]


def _payload_from_universo_result_row(row, *, team_keys, fallback_date='', fallback_round=''):
    home_name = str(
        _first(row, 'Nombre_equipo_local', 'nombre_equipo_local', 'equipo_local', 'local') or ''
    ).strip()
    away_name = str(
        _first(
            row,
            'Nombre_equipo_visitante',
            'nombre_equipo_visitante',
            'equipo_visitante',
            'visitante',
            'away',
        )
        or ''
    ).strip()
    home_keys = expand_team_lookup_variants(home_name)
    away_keys = expand_team_lookup_variants(away_name)
    home_code = str(
        _first(row, 'CodEquipo_local', 'cod_equipo_local', 'CodEquipoLocal', 'code_local') or ''
    ).strip().lower()
    away_code = str(
        _first(row, 'CodEquipo_visitante', 'cod_equipo_visitante', 'CodEquipoVisitante', 'code_away') or ''
    ).strip().lower()
    if home_code:
        home_keys.add(home_code)
    if away_code:
        away_keys.add(away_code)
    if team_keys & home_keys:
        opponent_name = away_name
        home_flag = True
        crest_url = absolute_universo_url(
            _first(row, 'url_img_visitante', 'url_img_visit', 'escudo_visitante', 'crest_away')
        )
        team_code = str(_first(row, 'CodEquipo_visitante', 'cod_equipo_visitante', 'code_away') or '').strip()
    elif team_keys & away_keys:
        opponent_name = home_name
        home_flag = False
        crest_url = absolute_universo_url(
            _first(row, 'url_img_local', 'url_img_loc', 'escudo_local', 'crest_home')
        )
        team_code = str(_first(row, 'CodEquipo_local', 'cod_equipo_local', 'code_local') or '').strip()
    else:
        return {}
    raw_date = str(
        _first(row, 'fecha', 'Fecha', 'date', 'fecha_partido', 'fechaPartido') or fallback_date or ''
    ).strip()
    date_iso = _parse_universo_result_date(raw_date)
    return normalize_next_match_payload(
        {
            'round': str(
                _first(row, 'nombre_jornada', 'NombreJornada', 'jornada', 'round') or fallback_round or ''
            ).strip(),
            'date': date_iso,
            'time': str(_first(row, 'hora', 'Hora', 'time', 'horario') or '').strip(),
            'location': str(_first(row, 'campojuego', 'CampoJuego', 'campo', 'location') or '').strip(),
            'opponent': {
                'name': opponent_name or 'Rival por confirmar',
                'full_name': opponent_name or 'Rival por confirmar',
                'crest_url': crest_url,
                'team_code': team_code,
            },
            'home': home_flag,
            'status': 'next',
            'source': 'universo-live',
        }
    )


def _parse_universo_result_date(raw_date):
    value = str(raw_date or '').strip()
    if 'T' in value:
        value = value.split('T', 1)[0].strip()
    if ' ' in value:
        value = value.split(' ', 1)[0].strip()
    if not value:
        return None
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _first(row, *keys):
    for key in keys:
        if not key:
            continue
        value = row.get(key)
        if value not in (None, ''):
            return value
    return ''


def load_preferred_next_match_payload(
    primary_team=None,
    competition_context=None,
    *,
    bind_context=True,
    bind_context_func=None,
    find_provider_func=None,
    load_cached_func=None,
    snapshot_supports_team_func=None,
):
    competition_context = competition_context or (
        WorkspaceCompetitionContext.objects
        .filter(Q(team=primary_team) | Q(workspace__primary_team=primary_team))
        .select_related('workspace', 'team', 'group')
        .first()
        if primary_team else None
    )
    provider_key = (
        str(getattr(competition_context, 'provider', '') or '').strip().lower()
        if competition_context else ''
    )
    if provider_key and provider_key != WorkspaceCompetitionContext.PROVIDER_UNIVERSO:
        return None
    if not competition_context:
        if not primary_team:
            return None
        if not (single_club_fallback_enabled() and bool(getattr(primary_team, 'is_primary', False))):
            return None
    if bind_context:
        if bind_context_func:
            competition_context = bind_context_func(competition_context, primary_team)
        else:
            from .universo_context_services import ensure_universo_context_binding

            competition_context = ensure_universo_context_binding(competition_context, primary_team)
    find_provider_func = find_provider_func or find_universo_next_match_for_context
    provider_next = find_provider_func(competition_context, primary_team)
    if next_match_payload_is_reliable(provider_next):
        return provider_next
    try:
        snapshot = getattr(competition_context, 'snapshot', None)
        if snapshot and isinstance(snapshot.next_match_payload, dict):
            snapshot_next = normalize_next_match_payload(dict(snapshot.next_match_payload))
            if next_match_payload_is_reliable(snapshot_next):
                return snapshot_next
    except Exception:
        pass

    snapshot = load_universo_snapshot()
    if snapshot_supports_team_func:
        can_use_external = snapshot_supports_team_func(snapshot, primary_team) if primary_team else False
    else:
        from .standings_services import universo_snapshot_supports_team

        can_use_external = universo_snapshot_supports_team(snapshot, primary_team) if primary_team else False
    if can_use_external and isinstance(snapshot, dict) and isinstance(snapshot.get('next_match'), dict):
        snapshot_next = normalize_next_match_payload(snapshot.get('next_match'))
        if next_match_payload_is_reliable(snapshot_next):
            return snapshot_next

    load_cached_func = load_cached_func or load_cached_next_match
    cached_next = load_cached_func() if can_use_external else None
    if isinstance(cached_next, dict):
        normalized_cached_next = normalize_next_match_payload(cached_next)
        if next_match_payload_is_reliable(normalized_cached_next):
            return normalized_cached_next
    return None


def load_cached_next_match(cache_path=None):
    cache_path = Path(cache_path) if cache_path else NEXT_MATCH_CACHE
    if not cache_path.exists():
        return None
    try:
        with cache_path.open(encoding='utf-8') as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                payload = normalize_next_match_payload(payload)
                payload.setdefault('status', 'next')
                status = (payload.get('status') or '').lower()
                source = str(payload.get('source') or '').strip().lower()
                date_raw = payload.get('date')
                if date_raw:
                    payload_date = parse_payload_date(date_raw)
                    today = timezone.localdate()
                    if payload_date:
                        if status == 'next' and payload_date < today:
                            return None
                        if status == 'latest' and payload_date < (today - timedelta(days=3)):
                            return None
                    elif status == 'next':
                        return None
                elif status == 'next' and source in {'', 'local-match'}:
                    return None
                return payload
    except Exception:
        return None
    return None


def next_match_payload_is_reliable(payload):
    if not isinstance(payload, dict):
        return False
    status = str(payload.get('status') or '').strip().lower()
    if status != 'next':
        return False
    source = str(payload.get('source') or '').strip().lower()
    opponent_name = payload_opponent_name(payload).strip().lower()
    if not opponent_name or opponent_name in {'rival por confirmar', 'rival desconocido'}:
        return False
    payload_date = parse_payload_date(payload.get('date'))
    if payload_date and payload_date < timezone.localdate():
        return False
    if not payload_date and source in {'', 'local-match'}:
        return False
    return True
