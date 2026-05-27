def preferred_event_source_by_match(primary_team, scope=None):
    from .views import preferred_event_source_by_match as view_preferred_event_source_by_match

    return view_preferred_event_source_by_match(primary_team, scope=scope)


def filter_stats_events(rows, preferred_sources=None):
    from .views import _filter_stats_events

    return _filter_stats_events(rows, preferred_sources=preferred_sources)


def compute_player_cards(primary_team, *, force_refresh=False, scope=None, tournament_name=None):
    from .views import compute_player_cards as view_compute_player_cards

    return view_compute_player_cards(
        primary_team,
        force_refresh=force_refresh,
        scope=scope,
        tournament_name=tournament_name,
    )
