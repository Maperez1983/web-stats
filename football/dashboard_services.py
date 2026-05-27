from . import stats_services
from .view_delegates import call_view


SCRAPE_LOCK_KEY = "football:refresh_scraping_running"
DASHBOARD_DELEGATED_VIEW_NAMES = (
    'compute_player_dashboard',
    'kpi_audit',
    'player_dashboard_page',
    'player_detail_page',
)


def compute_team_metrics_for_match(*args, **kwargs):
    return stats_services.compute_team_metrics_for_match(*args, **kwargs)


def compute_player_cards_for_match(*args, **kwargs):
    return stats_services.compute_player_cards_for_match(*args, **kwargs)


def compute_player_metrics(*args, **kwargs):
    return stats_services.compute_player_metrics(*args, **kwargs)


def compute_player_dashboard(*args, **kwargs):
    return call_view('compute_player_dashboard', *args, **kwargs)


def kpi_audit(*args, **kwargs):
    return call_view('kpi_audit', *args, **kwargs)


def player_dashboard_page(*args, **kwargs):
    return call_view('player_dashboard_page', *args, **kwargs)


def player_detail_page(*args, **kwargs):
    return call_view('player_detail_page', *args, **kwargs)
