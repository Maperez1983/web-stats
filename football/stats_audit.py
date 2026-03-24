from __future__ import annotations

from collections import defaultdict

from football.event_taxonomy import (
    FIELD_ZONES,
    is_goal_event,
    is_red_card_event,
    is_shot_attempt_event,
    is_yellow_card_event,
    map_zone_label,
    shots_needed_per_goal,
)
from football.models import TeamStanding
from football.query_helpers import _team_match_queryset, confirmed_events_queryset
from football.views import _filter_stats_events, compute_player_cards, preferred_event_source_by_match


def _normalized_match_key(match, primary_team):
    opponent = (
        match.away_team.display_name
        if match.home_team == primary_team and match.away_team
        else match.home_team.display_name
        if match.away_team == primary_team and match.home_team
        else 'Rival desconocido'
    )
    return (
        str(match.round or '').strip().lower(),
        str(match.date or ''),
        str(opponent or '').strip().lower(),
    )


def run_stats_audit(primary_team):
    if not primary_team:
        return {
            'ok': False,
            'issues': ['No hay equipo principal configurado.'],
            'notes': [],
            'summary': {},
            'details': {},
        }

    preferred_sources = preferred_event_source_by_match(primary_team)
    events = _filter_stats_events(
        confirmed_events_queryset()
        .filter(player__team=primary_team)
        .select_related('player', 'match', 'match__home_team', 'match__away_team')
        .order_by('match_id', 'minute', 'id'),
        preferred_sources=preferred_sources,
    )
    player_cards = compute_player_cards(primary_team)
    standings = list(
        TeamStanding.objects.filter(team=primary_team).select_related('season', 'group').order_by('-id')
    )
    standing = standings[0] if standings else None
    matches = list(
        _team_match_queryset(primary_team)
        .select_related('home_team', 'away_team')
        .order_by('date', 'id')
    )

    duplicate_signatures = defaultdict(list)
    for match in matches:
        duplicate_signatures[_normalized_match_key(match, primary_team)].append(match.id)
    duplicate_matches = [
        {'signature': key, 'match_ids': ids}
        for key, ids in duplicate_signatures.items()
        if key[0] and key[1] != 'None' and len(ids) > 1
    ]

    yellow_sum = sum(int(card.get('yellow_cards', 0) or 0) for card in player_cards)
    red_sum = sum(int(card.get('red_cards', 0) or 0) for card in player_cards)
    player_goal_sum = sum(int(card.get('goals', 0) or 0) for card in player_cards)
    shot_attempts_sum = sum(int(card.get('shot_attempts', 0) or 0) for card in player_cards)
    shots_on_target_sum = sum(int(card.get('shots_on_target', 0) or 0) for card in player_cards)

    event_goal_count = sum(1 for event in events if is_goal_event(event.event_type, event.result, event.observation))
    event_shot_attempts = sum(
        1 for event in events if is_shot_attempt_event(event.event_type, event.result, event.observation)
    )
    event_yellows = sum(1 for event in events if is_yellow_card_event(event.event_type, event.result, event.zone))
    event_reds = sum(1 for event in events if is_red_card_event(event.event_type, event.result, event.zone))
    measured_match_ids = {event.match_id for event in events if event.match_id}

    zone_counts = defaultdict(int)
    for event in events:
        zone_label = map_zone_label((event.zone or '').strip())
        if zone_label:
            zone_counts[zone_label] += 1
    mapped_zone_total = sum(zone_counts.values())
    field_zone_breakdown = []
    pct_sum = 0.0
    for zone in FIELD_ZONES:
        count = zone_counts.get(zone['key'], 0)
        pct = round((count / mapped_zone_total) * 100, 1) if mapped_zone_total else 0.0
        pct_sum += pct
        field_zone_breakdown.append(
            {
                'key': zone['key'],
                'count': count,
                'pct': pct,
            }
        )

    issues = []
    notes = []
    if duplicate_matches:
        issues.append(f'Partidos potencialmente duplicados detectados: {len(duplicate_matches)}')
    if abs(pct_sum - 100.0) > 1.0 and mapped_zone_total > 0:
        issues.append(f'El mapa de zonas no suma 100% (actual: {pct_sum:.1f}%).')
    if event_shot_attempts and shots_on_target_sum == 0 and event_goal_count > 0:
        issues.append('Hay goles en eventos pero los tiros a puerta agregados por jugador están a 0.')
    if standing and standing.goals_for is not None and measured_match_ids:
        notes.append(
            'Cobertura de acciones parcial: '
            f'goles reales de temporada {int(standing.goals_for)} vs goles medidos en eventos {event_goal_count} '
            f'en {len(measured_match_ids)} partidos medidos.'
        )
    if yellow_sum == 0 and event_yellows > 0:
        issues.append('Las tarjetas amarillas de plantilla están a 0 pese a existir eventos amarillos.')
    if red_sum == 0 and event_reds > 0:
        issues.append('Las tarjetas rojas de plantilla están a 0 pese a existir eventos rojos.')

    return {
        'ok': not issues,
        'issues': issues,
        'notes': notes,
        'summary': {
            'players': len(player_cards),
            'matches': len(matches),
            'measured_matches': len(measured_match_ids),
            'events': len(events),
            'standing_goals_for': int(standing.goals_for) if standing and standing.goals_for is not None else None,
            'player_goal_sum': player_goal_sum,
            'event_goal_count': event_goal_count,
            'event_shot_attempts': event_shot_attempts,
            'event_shots_per_goal': shots_needed_per_goal(event_shot_attempts, event_goal_count),
            'yellow_sum': yellow_sum,
            'red_sum': red_sum,
            'event_yellows': event_yellows,
            'event_reds': event_reds,
            'mapped_zone_total': mapped_zone_total,
            'field_zone_pct_sum': round(pct_sum, 1),
            'shot_attempts_sum': shot_attempts_sum,
            'shots_on_target_sum': shots_on_target_sum,
        },
        'details': {
            'duplicate_matches': duplicate_matches,
            'field_zone_breakdown': field_zone_breakdown,
        },
    }
