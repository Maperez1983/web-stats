import os
from collections import Counter

from django.core.cache import cache
from django.db.models import Count, Q
from django.templatetags.static import static

from .dashboard_cache import player_metrics_cache_key, team_metrics_cache_key
from .event_signatures import event_signature, is_manual_event_source
from .event_taxonomy import result_is_success
from .models import Match, MatchEvent, Workspace
from .player_media import resolve_player_photo_static_path
from .query_helpers import confirmed_events_queryset


PLAYER_METRICS_CACHE_SECONDS = int(os.getenv('PLAYER_METRICS_CACHE_SECONDS', '900'))
TEAM_METRICS_CACHE_SECONDS = int(os.getenv('TEAM_METRICS_CACHE_SECONDS', '900'))


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


def active_club_season_date_bounds_from_request(request):
    if request is None:
        return None, None
    try:
        from .workspace_context import get_active_workspace

        workspace = get_active_workspace(request)
        active_club_season = getattr(workspace, 'active_season', None) if workspace and getattr(workspace, 'kind', None) == Workspace.KIND_CLUB else None
        if active_club_season and bool(getattr(active_club_season, 'is_active', True)):
            return (
                getattr(active_club_season, 'start_date', None),
                getattr(active_club_season, 'end_date', None),
            )
    except Exception:
        pass
    return None, None


def _normalize_stats_scope(scope):
    scope_value = str(scope or Match.CONTEXT_LEAGUE).strip().lower() or Match.CONTEXT_LEAGUE
    if scope_value not in {Match.CONTEXT_LEAGUE, Match.CONTEXT_TOURNAMENT, Match.CONTEXT_FRIENDLY, 'all'}:
        return Match.CONTEXT_LEAGUE
    return scope_value


def _apply_match_scope(qs, scope_value):
    if scope_value == 'all':
        return qs
    if scope_value == Match.CONTEXT_LEAGUE:
        return qs.filter(Q(match__context=Match.CONTEXT_LEAGUE) | Q(match__context=''))
    return qs.filter(match__context=scope_value)


def compute_team_metrics(primary_team, scope=Match.CONTEXT_LEAGUE, request=None):
    if not primary_team:
        return {'total_events': 0, 'top_event_types': [], 'top_results': []}
    scope_value = _normalize_stats_scope(scope)
    date_start, date_end = active_club_season_date_bounds_from_request(request)
    cache_key = f'{team_metrics_cache_key(primary_team.id)}:{scope_value}'
    if not date_start and not date_end:
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and cached:
            return cached
    preferred_sources = preferred_event_source_by_match(primary_team, scope=scope_value)
    events_qs = (
        confirmed_events_queryset()
        .filter(player__team=primary_team)
        .select_related('match')
        .order_by('match_id', 'minute', 'id')
    )
    events_qs = _apply_match_scope(events_qs, scope_value)
    if date_start:
        events_qs = events_qs.filter(match__date__gte=date_start)
    if date_end:
        events_qs = events_qs.filter(match__date__lte=date_end)
    events = filter_stats_events(events_qs, preferred_sources=preferred_sources)
    payload = {
        'total_events': len(events),
        'top_event_types': [{'event': etype, 'count': count} for etype, count in Counter(event.event_type for event in events).most_common(5)],
        'top_results': [{'result': result, 'count': count} for result, count in Counter(event.result for event in events).most_common(5)],
    }
    if not date_start and not date_end:
        cache.set(cache_key, payload, TEAM_METRICS_CACHE_SECONDS)
    return payload


def compute_team_metrics_for_match(match, primary_team=None):
    events_qs = confirmed_events_queryset().filter(match=match)
    preferred_sources = None
    if primary_team:
        events_qs = events_qs.filter(player__team=primary_team)
        preferred_sources = preferred_event_source_by_match(primary_team)
    events = filter_stats_events(
        events_qs.select_related('player', 'match').order_by('minute', 'id'),
        preferred_sources=preferred_sources,
    )
    return {
        'total_events': len(events),
        'top_event_types': [{'event': etype, 'count': count} for etype, count in Counter(event.event_type for event in events).most_common(6)],
        'top_results': [{'result': result, 'count': count} for result, count in Counter(event.result for event in events).most_common(6)],
    }


def compute_player_metrics(primary_team, scope=Match.CONTEXT_LEAGUE, request=None):
    if not primary_team:
        return []
    scope_value = _normalize_stats_scope(scope)
    date_start, date_end = active_club_season_date_bounds_from_request(request)
    cache_key = f'{player_metrics_cache_key(primary_team.id)}:{scope_value}'
    if not date_start and not date_end:
        cached = cache.get(cache_key)
        if isinstance(cached, list) and cached:
            return cached
    preferred_sources = preferred_event_source_by_match(primary_team, scope=scope_value)
    events_qs = (
        confirmed_events_queryset()
        .filter(player__team=primary_team)
        .select_related('player', 'match')
        .order_by('match_id', 'minute', 'id')
    )
    events_qs = _apply_match_scope(events_qs, scope_value)
    if date_start:
        events_qs = events_qs.filter(match__date__gte=date_start)
    if date_end:
        events_qs = events_qs.filter(match__date__lte=date_end)
    events = filter_stats_events(events_qs, preferred_sources=preferred_sources)
    per_player = {}
    for event in events:
        player = event.player
        if not player:
            continue
        item = per_player.setdefault(
            player.id,
            {
                'player_id': player.id,
                'player': player.name,
                'actions': 0,
                'successes': 0,
            },
        )
        item['actions'] += 1
        if result_is_success(event.result):
            item['successes'] += 1
    result = sorted(per_player.values(), key=lambda item: (-item['actions'], item['player']))
    if not date_start and not date_end:
        cache.set(cache_key, result, PLAYER_METRICS_CACHE_SECONDS)
    return result


def compute_player_cards_for_match(match, primary_team, source_file=None):
    events = confirmed_events_queryset().filter(match=match, player__team=primary_team)
    if source_file:
        events = events.filter(source_file=source_file)
        preferred_sources = None
    else:
        preferred_sources = preferred_event_source_by_match(primary_team)
    rows = filter_stats_events(
        events.select_related('player', 'player__team', 'match').order_by('minute', 'id'),
        preferred_sources=preferred_sources,
    )
    per_player = {}
    for event in rows:
        player = event.player
        if not player:
            continue
        photo_path = resolve_player_photo_static_path(player)
        data = per_player.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number or '--',
                'photo_url': static(photo_path) if photo_path else '',
                'actions': 0,
                'successes': 0,
            },
        )
        data['actions'] += 1
        if result_is_success(event.result):
            data['successes'] += 1
    cards = list(per_player.values())
    for item in cards:
        total_actions = item['actions']
        success = item['successes']
        item['success_rate'] = round((success / total_actions) * 100, 1) if total_actions else 0
    return sorted(cards, key=lambda item: item['actions'], reverse=True)


def compute_player_cards(primary_team, *, force_refresh=False, scope=None, tournament_name=None, request=None):
    from .dashboard_services import compute_player_dashboard

    if not primary_team:
        return []
    dashboard_rows = compute_player_dashboard(
        primary_team,
        force_refresh=bool(force_refresh),
        scope=scope,
        tournament_name=tournament_name,
        request=request,
    )
    cards = []
    for row in dashboard_rows:
        total_actions = int(row.get('total_actions', 0) or 0)
        minutes = int(row.get('minutes', 0) or 0)
        actions_per90 = round((total_actions / minutes) * 90, 1) if minutes > 0 else 0.0
        goals = int(row.get('goals', 0) or 0)
        assists = int(row.get('assists', 0) or 0)
        cards.append(
            {
                'player_id': row.get('player_id'),
                'name': row.get('name'),
                'nickname': row.get('nickname') or '',
                'number': row.get('number'),
                'photo_url': row.get('photo_url', ''),
                'profile_label': row.get('profile_label') or row.get('profile') or '',
                'pj': int(row.get('pj', 0) or 0),
                'minutes': minutes,
                'goals': goals,
                'assists': assists,
                'goal_contrib': goals + assists,
                'yellow_cards': int(row.get('yellow_cards', 0) or 0),
                'red_cards': int(row.get('red_cards', 0) or 0),
                'actions': total_actions,
                'total_actions': total_actions,
                'actions_per90': actions_per90,
                'successes': int(row.get('successes', 0) or 0),
                'shot_attempts': int(row.get('shot_attempts', 0) or 0),
                'shots_on_target': int(row.get('shots_on_target', 0) or 0),
                'duels_total': int(row.get('duels_total', 0) or 0),
                'duels_won': int(row.get('duels_won', 0) or 0),
                'aerial_duels_total': int(row.get('aerial_duels_total', 0) or 0),
                'aerial_duels_won': int(row.get('aerial_duels_won', 0) or 0),
                'passes_completed': int(row.get('passes_completed', 0) or 0),
                'pass_attempts': int(row.get('pass_attempts', 0) or 0),
                'key_passes_completed': int(row.get('key_passes_completed', 0) or 0),
                'goalkeeper_saves': int(row.get('goalkeeper_saves', 0) or 0),
                'success_rate': float(row.get('success_rate', 0) or 0),
                'duel_rate': float(row.get('duel_rate', 0) or 0),
                'passes_accuracy': float(row.get('passes_accuracy', 0) or 0),
                'shots_accuracy': float(row.get('shots_accuracy', 0) or 0),
                'participation_pct': float(row.get('participation_pct', 0) or 0),
                'availability_pct': float(row.get('availability_pct', 0) or 0),
                'importance_score': float(row.get('importance_score', 0) or 0),
                'influence_score': float(row.get('influence_score', 0) or 0),
                'has_active_injury': bool(row.get('has_active_injury')),
                'is_sanctioned': bool(row.get('is_sanctioned')),
                'is_apercibido': bool(row.get('is_apercibido')),
                'position': row.get('position') or '',
                'matches': row.get('matches') if isinstance(row.get('matches'), list) else [],
            }
        )
    return sorted(cards, key=lambda entry: (-entry['goals'], -entry['pj'], entry['name']))
