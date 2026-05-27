from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils.module_loading import import_string

from .library_repositories import (
    LIBRARY_MICROCYCLE_MARKER,
    LIBRARY_REPOSITORY_AI_TRAINER,
    LIBRARY_REPOSITORY_CHOICES,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    library_repository_for_task,
    normalize_library_repository,
)


def _views_func(name):
    return import_string(f'football.views.{name}')


def task_scope_for_item(task):
    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    scope = str(meta.get('scope') or '').strip()
    return scope or 'coach'


def task_preview_needs_refresh(task):
    if not task:
        return False
    preview_name = str(getattr(task, 'task_preview_image', '') or '').strip()
    if not preview_name:
        return True
    try:
        if not default_storage.exists(preview_name):
            return True
    except Exception:
        return True
    cache_key = f'football:preview-quality:{preview_name}'
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached)
    try:
        with default_storage.open(preview_name, 'rb') as handle:
            raw = handle.read()
        needs_refresh = is_preview_quality_low(raw)
    except Exception:
        needs_refresh = True
    cache.set(cache_key, bool(needs_refresh), 60 * 60 * 6)
    return bool(needs_refresh)


def is_preview_quality_low(raw_bytes):
    metrics = analyze_preview_image_bytes(raw_bytes)
    if not metrics:
        return False
    score = float(metrics.get('score') or 0.0)
    area = int(metrics.get('area') or 0)
    white_ratio = float(metrics.get('white_ratio') or 0.0)
    green_ratio = float(metrics.get('green_ratio') or 0.0)
    if area < 260 * 170:
        return True
    if score < 10.0:
        return True
    if white_ratio > 0.72 and green_ratio < 0.08:
        return True
    return False


def task_analysis_needs_refresh(task):
    return _views_func('_task_analysis_needs_refresh')(task)


def ensure_library_task_preview(task, force=False, prefer_render=False):
    return _views_func('_ensure_library_task_preview')(task, force=force, prefer_render=prefer_render)


def maybe_render_task_preview_server_side(task, *, force=False):
    return _views_func('_maybe_render_task_preview_server_side')(task, force=force)


def analyze_preview_image_bytes(raw_bytes):
    return _views_func('_analyze_preview_image_bytes')(raw_bytes)


def cleanup_task_joined_text_fields(task):
    return _views_func('_cleanup_task_joined_text_fields')(task)


def refresh_task_from_pdf_analysis(task):
    return _views_func('_refresh_task_from_pdf_analysis')(task)


def learn_task_blueprint_from_task(*, team, task, scope_key: str = '', actor_username: str = ''):
    return _views_func('_learn_task_blueprint_from_task')(
        team=team,
        task=task,
        scope_key=scope_key,
        actor_username=actor_username,
    )


def ensure_library_task_preview_legacy(task, force=False, prefer_render=False):
    return ensure_library_task_preview(task, force=force, prefer_render=prefer_render)
