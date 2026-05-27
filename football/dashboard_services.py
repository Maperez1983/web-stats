from . import stats_services


SCRAPE_LOCK_KEY = "football:refresh_scraping_running"


def compute_team_metrics_for_match(*args, **kwargs):
    return stats_services.compute_team_metrics_for_match(*args, **kwargs)


def compute_player_cards_for_match(*args, **kwargs):
    return stats_services.compute_player_cards_for_match(*args, **kwargs)


def compute_player_metrics(*args, **kwargs):
    return stats_services.compute_player_metrics(*args, **kwargs)


def compute_player_dashboard(*args, **kwargs):
    from .views import compute_player_dashboard as view

    return view(*args, **kwargs)


def kpi_audit(*args, **kwargs):
    from .views import kpi_audit as view

    return view(*args, **kwargs)


def player_dashboard_page(*args, **kwargs):
    from .views import player_dashboard_page as view

    return view(*args, **kwargs)


def player_detail_page(*args, **kwargs):
    from .views import player_detail_page as view

    return view(*args, **kwargs)
