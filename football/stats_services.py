from django.db.models import Count, Q
from django.utils.module_loading import import_string

from .event_signatures import event_signature, is_manual_event_source
from .models import Match, MatchEvent


def preferred_event_source_by_match(primary_team, scope=None):
    """
    Choose one authoritative source per match to avoid cross-source double counting.
    Priority:
    1) Any `registro-acciones` events for that match.
    2) Otherwise, most frequent non-empty source_file.
    """
    if not primary_team:
        return {}
    scope_value = str(scope or '').strip().lower()
    if scope_value not in {Match.CONTEXT_LEAGUE, Match.CONTEXT_TOURNAMENT, Match.CONTEXT_FRIENDLY, 'all', ''}:
        scope_value = ''
    team_events = (
        MatchEvent.objects
        .filter(player__team=primary_team)
        .filter(
            Q(source_file='registro-acciones')
            | ~Q(system='touch-field')
        )
    )
    if scope_value and scope_value != 'all':
        if scope_value == Match.CONTEXT_LEAGUE:
            team_events = team_events.filter(Q(match__context=Match.CONTEXT_LEAGUE) | Q(match__context=''))
        else:
            team_events = team_events.filter(match__context=scope_value)
    preferred = {}
    registro_match_ids = set(
        team_events.filter(source_file='registro-acciones')
        .values_list('match_id', flat=True)
        .distinct()
    )
    for match_id in registro_match_ids:
        preferred[match_id] = 'registro-acciones'

    fallback_rows = (
        team_events.exclude(source_file__isnull=True)
        .exclude(source_file__exact='')
        .values('match_id', 'source_file')
        .annotate(c=Count('id'))
        .order_by('match_id', '-c', 'source_file')
    )
    seen = set(preferred.keys())
    for row in fallback_rows:
        match_id = row['match_id']
        if match_id in seen:
            continue
        preferred[match_id] = row['source_file']
        seen.add(match_id)
    return preferred


def event_matches_stats_source(event, preferred_sources=None):
    if not preferred_sources:
        return True
    preferred_source = preferred_sources.get(getattr(event, 'match_id', None))
    if not preferred_source:
        return True
    current_source = (getattr(event, 'source_file', '') or '').strip()
    return current_source == preferred_source or is_manual_event_source(current_source)


def canonical_match_id(match_id):
    try:
        return int(match_id or 0)
    except Exception:
        return 0


def filter_stats_events(rows, preferred_sources=None):
    seen_signatures = set()
    filtered = []
    for event in rows:
        if not event_matches_stats_source(event, preferred_sources):
            continue
        signature = event_signature(event)
        try:
            if isinstance(signature, tuple) and signature and isinstance(signature[0], int):
                signature = (canonical_match_id(signature[0]), *signature[1:])
        except Exception:
            pass
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        filtered.append(event)
    return filtered


def compute_player_cards(primary_team, *, force_refresh=False, scope=None, tournament_name=None):
    return import_string('football.views.compute_player_cards')(
        primary_team,
        force_refresh=force_refresh,
        scope=scope,
        tournament_name=tournament_name,
    )
