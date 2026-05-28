from . import stats_services
from .view_delegates import install_view_delegates


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


install_view_delegates(globals(), DASHBOARD_DELEGATED_VIEW_NAMES)
