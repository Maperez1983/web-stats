import io
import re

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils.module_loading import import_string

from .services import _parse_int

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

TASK_PDF_PARSE_VERSION = 4

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
    if not task or not getattr(task, 'task_pdf', None):
        return False
    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    parser_version = _parse_int(analysis_meta.get('parser_version')) or 0
    if parser_version < TASK_PDF_PARSE_VERSION:
        return True
    summary = str(analysis_meta.get('summary') or '')
    if text_has_quality_issues(summary):
        return True
    if text_has_quality_issues(str(getattr(task, 'title', '') or '')):
        return True
    if text_has_quality_issues(str(getattr(task, 'objective', '') or '')):
        return True
    return False


def text_has_quality_issues(value):
    text = str(value or '').strip()
    if not text:
        return False
    if re.search(r'\b[A-ZÁÉÍÓÚÜÑ]{12,}\b', text):
        return True
    if re.search(r'[,;:](\S)', text):
        return True
    if re.search(r'\s{2,}', text):
        return True
    if len(text) >= 8 and text.isupper():
        return True
    return False


def ensure_library_task_preview(task, force=False, prefer_render=False):
    return _views_func('_ensure_library_task_preview')(task, force=force, prefer_render=prefer_render)


def maybe_render_task_preview_server_side(task, *, force=False):
    return _views_func('_maybe_render_task_preview_server_side')(task, force=force)


def analyze_preview_image_bytes(raw_bytes):
    if Image is None or not raw_bytes:
        return None
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb = img.convert('RGB')
            width, height = rgb.size
            if width <= 0 or height <= 0:
                return None
            sample = rgb.copy()
            sample.thumbnail((128, 128))
            pixels = list(sample.getdata())
            total = max(1, len(pixels))
            greenish = 0
            whitish = 0
            darkish = 0
            colorful = 0
            for r, g, b in pixels:
                if g > 70 and g > (r + 14) and g > (b + 10):
                    greenish += 1
                if r > 232 and g > 232 and b > 232:
                    whitish += 1
                if r < 30 and g < 30 and b < 30:
                    darkish += 1
                if (max(r, g, b) - min(r, g, b)) >= 24:
                    colorful += 1
            green_ratio = greenish / total
            white_ratio = whitish / total
            dark_ratio = darkish / total
            color_ratio = colorful / total
            area = width * height
            aspect = width / max(1.0, float(height))

            score = 0.0
            score += min(area / float(1280 * 720), 2.6) * 28.0
            score += green_ratio * 46.0
            score += color_ratio * 16.0
            if 0.95 <= aspect <= 2.35:
                score += 8.0
            if 1.15 <= aspect <= 2.05:
                score += 6.0
            score -= white_ratio * 44.0
            if min(width, height) < 210:
                score -= 26.0
            if white_ratio > 0.78 and green_ratio < 0.06:
                score -= 48.0
            if dark_ratio > 0.88:
                score -= 20.0

            return {
                'width': int(width),
                'height': int(height),
                'area': int(area),
                'aspect': float(aspect),
                'green_ratio': float(green_ratio),
                'white_ratio': float(white_ratio),
                'dark_ratio': float(dark_ratio),
                'score': float(score),
            }
    except Exception:
        return None


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
