from __future__ import annotations

from football.models import PlayerStatistic, Season
from football.services import _parse_int


MANUAL_BASE_STAT_NAMES = (
    'manual_pj',
    'manual_pt',
    'manual_minutes',
    'manual_goals',
    'manual_assists',
    'manual_yellow_cards',
    'manual_red_cards',
)


def resolve_stats_season(primary_team):
    if not primary_team:
        return None
    if primary_team.group and primary_team.group.season:
        return primary_team.group.season
    return Season.objects.filter(is_current=True).order_by('-start_date', '-id').first()


def season_display_name(season):
    if not season:
        return 'Temporada actual'
    if getattr(season, 'name', None):
        return season.name
    start_date = getattr(season, 'start_date', None)
    end_date = getattr(season, 'end_date', None)
    if start_date and end_date:
        return f'{start_date.year}/{end_date.year}'
    if start_date:
        return str(start_date.year)
    return 'Temporada actual'


def get_manual_player_base_overrides(primary_team, season=None):
    if not primary_team:
        return {}
    season = season or resolve_stats_season(primary_team)
    if season is None:
        return {}
    stats = (
        PlayerStatistic.objects.filter(
            player__team=primary_team,
            season=season,
            match__isnull=True,
            context='manual-base',
            name__in=MANUAL_BASE_STAT_NAMES,
        )
        .select_related('player')
    )
    overrides = {}
    for stat in stats:
        player_data = overrides.setdefault(stat.player_id, {})
        value = _parse_int(stat.value) or 0
        if stat.name == 'manual_pj':
            player_data['pj'] = value
        elif stat.name == 'manual_pt':
            player_data['pt'] = value
        elif stat.name == 'manual_minutes':
            player_data['minutes'] = value
        elif stat.name == 'manual_goals':
            player_data['goals'] = value
        elif stat.name == 'manual_assists':
            player_data['assists'] = value
        elif stat.name == 'manual_yellow_cards':
            player_data['yellow_cards'] = value
        elif stat.name == 'manual_red_cards':
            player_data['red_cards'] = value
    return overrides


def save_manual_player_base_overrides(*, player, season, values):
    if not player or not season:
        return
    for stat_name, stat_value in values.items():
        queryset = PlayerStatistic.objects.filter(
            player=player,
            season=season,
            match=None,
            name=stat_name,
            context='manual-base',
        )
        normalized_value = _parse_int(stat_value) or 0
        stat = queryset.order_by('-id').first()
        if stat:
            duplicates = queryset.exclude(id=stat.id)
            if duplicates.exists():
                duplicates.delete()
            if stat.value != normalized_value:
                stat.value = normalized_value
                stat.save(update_fields=['value'])
        else:
            PlayerStatistic.objects.create(
                player=player,
                season=season,
                match=None,
                name=stat_name,
                context='manual-base',
                value=normalized_value,
            )
