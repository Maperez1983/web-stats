from django.db.models import Q
from django.utils import timezone

from .match_payload_services import normalize_next_match_payload
from .models import Team
from .query_helpers import _normalize_team_lookup_key, get_current_convocation_record
from .team_media_services import (
    absolute_universo_url,
    build_universo_capture_team_lookup,
    resolve_team_crest_url,
    sanitize_universo_external_image,
)
from .universo_snapshot_services import load_universo_snapshot


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
