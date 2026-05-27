from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from .models import Match


def normalize_next_match_payload(payload):
    if not isinstance(payload, dict):
        return payload
    opponent = payload.get('opponent')
    if isinstance(opponent, str):
        clean_name = opponent.strip() or 'Rival por confirmar'
        payload['opponent'] = {
            'name': clean_name,
            'full_name': clean_name,
            'crest_url': '',
            'kit2d_url': '',
            'team_code': '',
        }
    elif isinstance(opponent, dict):
        name = str(opponent.get('name') or opponent.get('full_name') or '').strip()
        full_name = str(opponent.get('full_name') or name).strip()
        payload['opponent'] = {
            'name': name or 'Rival por confirmar',
            'full_name': full_name or name or 'Rival por confirmar',
            'crest_url': str(opponent.get('crest_url') or '').strip(),
            'kit2d_url': str(opponent.get('kit2d_url') or '').strip(),
            'team_code': str(opponent.get('team_code') or '').strip(),
        }
    else:
        fallback = str(payload.get('rival') or '').strip()
        payload['opponent'] = {
            'name': fallback or 'Rival por confirmar',
            'full_name': fallback or 'Rival por confirmar',
            'crest_url': '',
            'kit2d_url': '',
            'team_code': '',
        }
    return payload


def parse_payload_date(raw):
    if not raw:
        return None
    value = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_payload_time(raw):
    if not raw:
        return None
    value = str(raw).strip()
    for fmt in ('%H:%M', '%H.%M', '%H,%M'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def payload_opponent_name(payload):
    if not isinstance(payload, dict):
        return ''
    opponent = payload.get('opponent')
    if isinstance(opponent, dict):
        return str(opponent.get('full_name') or opponent.get('name') or '').strip()
    if isinstance(opponent, str):
        return opponent.strip()
    return str(payload.get('rival') or '').strip()


def next_match_payload_is_usable(payload):
    if not isinstance(payload, dict):
        return False
    status = str(payload.get('status') or '').strip().lower()
    if status != 'next':
        return False
    opponent_name = payload_opponent_name(payload).strip().lower()
    if not opponent_name or opponent_name in {'rival por confirmar', 'rival desconocido'}:
        return False
    round_value = str(payload.get('round') or '').strip()
    if not round_value:
        return False
    return True


def build_match_payload(match, primary_team, status):
    opponent = match.away_team if match.home_team == primary_team else match.home_team
    return normalize_next_match_payload({
        'round': match.round,
        'date': match.date.isoformat() if match.date else None,
        'location': match.location,
        'opponent': {
            'name': opponent.name if opponent else 'Rival desconocido',
            'full_name': opponent.name if opponent else 'Rival desconocido',
            'crest_url': '',
            'team_code': '',
        },
        'home': match.home_team == primary_team,
        'status': status,
        'source': 'local-match',
    })


def build_local_next_match_payload(primary_team):
    if not primary_team:
        return {}
    today = timezone.localdate()
    base_qs = (
        Match.objects
        .filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .select_related('home_team', 'away_team')
    )
    scoped_qs = base_qs.filter(group=primary_team.group) if getattr(primary_team, 'group_id', None) else base_qs
    match_obj = (
        scoped_qs.filter(date__gte=today).order_by('date', 'id').first()
        or base_qs.filter(date__gte=today).order_by('date', 'id').first()
    )
    if not match_obj:
        match_obj = (
            scoped_qs.exclude(date__isnull=True).order_by('-date', '-id').first()
            or base_qs.exclude(date__isnull=True).order_by('-date', '-id').first()
            or scoped_qs.order_by('-id').first()
            or base_qs.order_by('-id').first()
        )
    if not match_obj:
        return {}
    return build_match_payload(match_obj, primary_team, status='next')


def build_workspace_schedule_payload(primary_team, *, limit=8):
    if not primary_team:
        return []
    matches = (
        Match.objects
        .filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .select_related('home_team', 'away_team')
        .order_by('date', 'id')[:limit]
    )
    payload = []
    for match in matches:
        payload.append(
            build_match_payload(
                match,
                primary_team,
                status='next' if match.date and match.date >= timezone.localdate() else 'latest',
            )
        )
    return payload
