from django.utils.module_loading import import_string


SCRAPE_LOCK_KEY = "football:refresh_scraping_running"


def _views_func(name):
    return import_string(f'football.views.{name}')


def compute_team_metrics_for_match(*args, **kwargs):
    return _views_func('compute_team_metrics_for_match')(*args, **kwargs)


def compute_player_cards_for_match(*args, **kwargs):
    return _views_func('compute_player_cards_for_match')(*args, **kwargs)


def compute_player_metrics(*args, **kwargs):
    return _views_func('compute_player_metrics')(*args, **kwargs)


def compute_player_dashboard(*args, **kwargs):
    return _views_func('compute_player_dashboard')(*args, **kwargs)


def kpi_audit(*args, **kwargs):
    return _views_func('kpi_audit')(*args, **kwargs)


def player_dashboard_page(*args, **kwargs):
    return _views_func('player_dashboard_page')(*args, **kwargs)


def player_detail_page(*args, **kwargs):
    return _views_func('player_detail_page')(*args, **kwargs)
