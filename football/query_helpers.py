from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from django.core.cache import cache
from django.db.models import Max, Q
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from football.event_taxonomy import extract_round_number, is_red_card_event
from football.models import (
    ConvocationRecord,
    Match,
    MatchEvent,
    MatchReport,
    Player,
    PlayerInjuryRecord,
    PlayerStatistic,
    Team,
)
from football.services import _parse_int


def _normalize_team_lookup_key(value):
    text = str(value or '').strip()
    if not text:
        return ''
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r'[^a-z0-9]+', '', normalized.lower())
    return normalized


def _team_name_signature(value):
    text = str(value or '').strip()
    if not text:
        return ()
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    tokens = [tok for tok in re.findall(r'[a-z0-9]+', normalized) if tok]
    if not tokens:
        return ()
    return tuple(sorted(tokens))


def is_injury_record_active(record, today=None):
    if not record or not getattr(record, 'is_active', False):
        return False
    reference_day = today or timezone.localdate()
    return_date = getattr(record, 'return_date', None)
    if return_date and return_date <= reference_day:
        return False
    return True


def get_active_injury_player_ids(player_ids):
    normalized_ids = [int(pid) for pid in set(player_ids or []) if pid]
    if not normalized_ids:
        return set()
    try:
        return set(
            PlayerInjuryRecord.objects
            .filter(player_id__in=normalized_ids, is_active=True)
            .filter(Q(return_date__isnull=True) | Q(return_date__gt=timezone.localdate()))
            .values_list('player_id', flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def _team_match_queryset(primary_team):
    if not primary_team:
        return Match.objects.none()
    direct_filter = Q(home_team=primary_team) | Q(away_team=primary_team)
    team_signature = _team_name_signature(primary_team.name)
    if not team_signature:
        return Match.objects.filter(direct_filter).select_related('home_team', 'away_team')

    alias_cache_key = f'football:team_alias_ids:{int(primary_team.id)}'
    alias_ids = cache.get(alias_cache_key)
    if alias_ids is None:
        alias_ids = []
        primary_lookup = _normalize_team_lookup_key(primary_team.name)
        for candidate in Team.objects.exclude(id=primary_team.id).only('id', 'name'):
            candidate_signature = _team_name_signature(candidate.name)
            candidate_lookup = _normalize_team_lookup_key(candidate.name)
            same_signature = candidate_signature == team_signature
            fuzzy_same_team = bool(
                primary_lookup
                and candidate_lookup
                and (
                    primary_lookup in candidate_lookup
                    or candidate_lookup in primary_lookup
                    or ('benagalbon' in primary_lookup and 'benagalbon' in candidate_lookup)
                )
            )
            if same_signature or fuzzy_same_team:
                alias_ids.append(candidate.id)
        cache.set(alias_cache_key, alias_ids, 60 * 15)
    if alias_ids:
        direct_filter = direct_filter | Q(home_team_id__in=alias_ids) | Q(away_team_id__in=alias_ids)

    extra_match_cache_key = f'football:team_extra_match_ids:{int(primary_team.id)}'
    cached_extra_ids = cache.get(extra_match_cache_key)
    if isinstance(cached_extra_ids, dict):
        event_match_ids = cached_extra_ids.get('events') or []
        convocation_match_ids = cached_extra_ids.get('convocations') or []
        player_stat_match_ids = cached_extra_ids.get('player_stats') or []
        report_match_ids = cached_extra_ids.get('reports') or []
    else:
        event_match_ids = list(
            MatchEvent.objects
            .filter(player__team=primary_team)
            .values_list('match_id', flat=True)
            .distinct()
        )
        convocation_match_ids = list(
            ConvocationRecord.objects
            .filter(team=primary_team, match_id__isnull=False)
            .values_list('match_id', flat=True)
            .distinct()
        )
        player_stat_match_ids = list(
            PlayerStatistic.objects
            .filter(player__team=primary_team, match_id__isnull=False)
            .values_list('match_id', flat=True)
            .distinct()
        )
        report_match_ids = list(
            MatchReport.objects
            .filter(match_id__isnull=False)
            .values_list('match_id', flat=True)
            .distinct()
        )
        cache.set(
            extra_match_cache_key,
            {
                'events': event_match_ids,
                'convocations': convocation_match_ids,
                'player_stats': player_stat_match_ids,
                'reports': report_match_ids,
            },
            60 * 5,
        )
    if event_match_ids:
        direct_filter = direct_filter | Q(id__in=event_match_ids)
    if convocation_match_ids:
        direct_filter = direct_filter | Q(id__in=convocation_match_ids)
    if player_stat_match_ids:
        direct_filter = direct_filter | Q(id__in=player_stat_match_ids)
    if report_match_ids:
        direct_filter = direct_filter | Q(id__in=report_match_ids)

    return Match.objects.filter(direct_filter).select_related('home_team', 'away_team').distinct()


def get_active_match(primary_team):
    qs = _team_match_queryset(primary_team)
    if not qs.exists():
        return None
    today = timezone.localdate()
    upcoming = qs.filter(date__gte=today).order_by('date').first()
    if upcoming:
        return upcoming
    undated_next = list(qs.filter(date__isnull=True))
    if undated_next:
        undated_next.sort(
            key=lambda match: (
                extract_round_number(match.round or '') or -1,
                match.id or 0,
            ),
            reverse=True,
        )
        return undated_next[0]
    latest = qs.exclude(date__isnull=True).order_by('-date').first()
    if latest:
        return latest
    return qs.order_by('-id').first()


def get_requested_match(request, primary_team):
    if not primary_team:
        return None
    raw_match_id = request.GET.get('match_id') or request.POST.get('match_id')
    match_id = _parse_int(raw_match_id)
    if not match_id:
        return None
    return _team_match_queryset(primary_team).filter(id=match_id).first()


def get_latest_pizarra_match(primary_team):
    if not primary_team:
        return None
    return (
        _team_match_queryset(primary_team)
        .filter(events__source_file='registro-acciones', events__system='touch-field-final')
        .annotate(last_event_at=Max('events__created_at'))
        .order_by('-last_event_at', '-id')
        .first()
    )


def get_previous_match(primary_team, reference_match=None):
    if not primary_team:
        return None
    qs = _team_match_queryset(primary_team)
    if not qs.exists():
        return None
    if reference_match and reference_match.date:
        previous = (
            qs.exclude(id=reference_match.id)
            .filter(date__lt=reference_match.date)
            .order_by('-date', '-id')
            .first()
        )
        if previous:
            return previous
    today = timezone.localdate()
    previous = qs.filter(date__lt=today).order_by('-date', '-id').first()
    if previous:
        return previous
    return None


def confirmed_events_queryset():
    return MatchEvent.objects.exclude(system='touch-field')


def get_sanctioned_player_ids_from_previous_round(primary_team, reference_match=None):
    previous_match = get_previous_match(primary_team, reference_match=reference_match)
    if not previous_match:
        return set()
    sanctioned_ids = set()
    events = (
        confirmed_events_queryset()
        .filter(match=previous_match, player__team=primary_team)
        .select_related('player')
    )
    for event in events:
        if event.player_id and is_red_card_event(event.event_type, event.result, event.zone):
            sanctioned_ids.add(event.player_id)
    return sanctioned_ids


def is_manual_sanction_active(player, today=None):
    if not player or not getattr(player, 'manual_sanction_active', False):
        return False
    reference_day = today or timezone.localdate()
    until_date = getattr(player, 'manual_sanction_until', None)
    if until_date and until_date < reference_day:
        return False
    return True


def get_current_convocation_record(team, match=None, fallback_to_latest=True):
    if not team:
        return None
    qs = ConvocationRecord.objects.filter(team=team, is_current=True).prefetch_related('players')
    if match:
        by_match = qs.filter(match=match).order_by('-created_at').first()
        if by_match:
            return by_match
        if not fallback_to_latest:
            return None
    return qs.order_by('-created_at').first()


def get_current_convocation(team, match=None):
    record = get_current_convocation_record(team, match=match)
    if record:
        return record.players.order_by('name')
    return Player.objects.filter(team=team, is_active=True).order_by('name')


def parse_match_date_from_ui(raw_value):
    value = (raw_value or '').strip()
    if not value:
        return None
    date_part = value.split('·', 1)[0].strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_part, fmt).date()
        except ValueError:
            continue
    return None
