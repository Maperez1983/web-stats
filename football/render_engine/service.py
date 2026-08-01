from __future__ import annotations

import base64
import uuid
from typing import Any, Dict, Optional

from django.core.files.base import ContentFile

from ..preview_render import render_task_preview_png
from .normalizer import (
    extract_task_canvas_state,
    normalize_animation_timeline,
    parse_int,
    resolve_task_meta,
    resolve_task_tactical_layout,
    resolve_task_team,
)
from .renderer_2d import render_task_preview_2d
from .renderer_3d import build_task_preview_3d_embed_url, render_task_preview_3d
from .timeline import (
    build_animation_frame_cards,
    build_animation_object_tracks,
    build_animation_object_tracks_from_simulation_pro,
    summarize_animation_object_tracks,
)


def _is_live_preview_mode(request: Any) -> bool:
    resolver_name = str(getattr(getattr(request, 'resolver_match', None), 'url_name', '') or '').strip()
    live_preview_mode = resolver_name in {'sessions-task-pdf-preview', 'task-studio-task-pdf-preview'}
    if not live_preview_mode and request is not None:
        live_preview_mode = str(request.GET.get('live_preview_3d') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    return live_preview_mode


def _resolve_preview_fallback_url(task: Any, request: Any) -> str:
    preview_url = str(getattr(request, '_task_render_preview_url', '') or '').strip() if request is not None else ''
    if preview_url:
        return preview_url
    from .. import views

    try:
        if getattr(task, 'task_preview_image', None):
            preview_url = views._file_field_as_data_url(task.task_preview_image)
    except Exception:
        preview_url = ''
    if preview_url:
        return preview_url
    try:
        embedded = views._embedded_preview_bytes_from_task(task)
        if embedded:
            raw, mime = embedded
            return views._image_bytes_as_small_data_uri(
                raw,
                mime_type=mime or 'image/jpeg',
                max_width=3200,
                max_height=2400,
                quality=88,
            )
    except Exception:
        return ''
    return ''


def _resolve_task_preview_image_url(task: Any, *, prefer_file_url: bool = False) -> str:
    from .. import views

    try:
        if getattr(task, 'task_preview_image', None):
            if prefer_file_url:
                try:
                    return str(task.task_preview_image.url or '').strip()
                except Exception:
                    pass
            return str(views._file_field_as_data_url(task.task_preview_image) or '').strip()
    except Exception:
        return ''
    return ''


def _decode_image_data_url(data_url: str) -> tuple[bytes, str]:
    raw = str(data_url or '').strip()
    if not raw.startswith('data:image/') or ';base64,' not in raw:
        return b'', ''
    header, payload = raw.split(';base64,', 1)
    mime_type = header.replace('data:', '', 1).strip().lower()
    try:
        return base64.b64decode(payload), mime_type
    except Exception:
        return b'', ''


def _persist_generated_task_preview_image(task: Any, preview_url: str) -> str:
    if not task or getattr(task, 'task_preview_image', None):
        return ''
    raw_bytes, mime_type = _decode_image_data_url(preview_url)
    if not raw_bytes:
        return ''
    extension = {
        'image/png': 'png',
        'image/jpeg': 'jpg',
        'image/webp': 'webp',
    }.get(mime_type, 'png')
    filename = f"task-{getattr(task, 'id', 'preview')}-sheet-2d-{uuid.uuid4().hex[:10]}.{extension}"
    try:
        task.task_preview_image.save(filename, ContentFile(raw_bytes), save=True)
    except Exception:
        return ''
    return _resolve_task_preview_image_url(task)


def _normalize_preview_grass_style(meta: Dict[str, Any], variant: str = '2d') -> str:
    raw_grass_style = str(meta.get('pitch_grass_style') or 'broadcast_premium').strip().lower()
    normalized_variant = '3d' if str(variant or '').strip().lower() == '3d' else '2d'
    if normalized_variant == '3d':
        return 'stadium_top'
    if raw_grass_style in {'stadium_top', 'stadium_top_h', 'stadium_top_v', 'stadium_native'}:
        return 'broadcast_premium'
    if raw_grass_style in {'classic', 'broadcast', 'broadcast_premium', 'realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'whiteboard', 'blackboard'}:
        return raw_grass_style
    return 'broadcast_premium'


def _first_distinct_animation_frame(
    animation_frame_cards: list[dict[str, Any]],
    *,
    base_preview_2d_url: str,
    base_preview_3d_url: str,
) -> Dict[str, Any]:
    normalized_base_2d = str(base_preview_2d_url or '').strip()
    normalized_base_3d = str(base_preview_3d_url or '').strip()
    for frame_card in animation_frame_cards:
        if not isinstance(frame_card, dict) or frame_card.get('is_fallback'):
            continue
        frame_preview_2d = str(frame_card.get('preview_2d_url') or '').strip()
        frame_preview_3d = str(frame_card.get('preview_3d_url') or '').strip()
        differs_2d = bool(frame_preview_2d) and frame_preview_2d != normalized_base_2d
        differs_3d = bool(frame_preview_3d) and frame_preview_3d != normalized_base_3d
        if differs_2d or differs_3d:
            return frame_card
    return {}


def build_task_render_bundle(task: Any, request: Any = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from .. import views

    opts = options if isinstance(options, dict) else {}
    include_animation_cards = bool(opts.get('include_animation_cards', True))
    include_3d_snapshot = bool(opts.get('include_3d_snapshot', True))
    prefer_file_urls = bool(opts.get('prefer_file_urls', False))
    force_3d_embed_url = bool(opts.get('force_3d_embed_url', False))

    tactical_layout = resolve_task_tactical_layout(task)
    meta = resolve_task_meta(task)
    graphic_editor = meta.get('graphic_editor') if isinstance(meta.get('graphic_editor'), dict) else {}
    orientation_key = str(meta.get('pitch_orientation') or 'landscape').strip().lower()
    default_canvas_width = 684 if orientation_key == 'portrait' else 1054
    default_canvas_height = 1054 if orientation_key == 'portrait' else 684
    frame_canvas_width = parse_int(graphic_editor.get('canvas_width')) or default_canvas_width
    frame_canvas_height = parse_int(graphic_editor.get('canvas_height')) or default_canvas_height
    preview_url = _resolve_preview_fallback_url(task, request)
    team = resolve_task_team(task)
    animation_frames = normalize_animation_timeline(tactical_layout.get('timeline') if isinstance(tactical_layout, dict) else [])
    live_preview_mode = _is_live_preview_mode(request)

    def _render_variant_preview_url(canvas_state: Dict[str, Any], variant: str = '2d', *, fallback_to_primary: bool = False) -> str:
        normalized_variant = '3d' if str(variant or '').strip().lower() == '3d' else '2d'
        safe_state = canvas_state if isinstance(canvas_state, dict) else {'objects': []}
        has_objects = isinstance(safe_state.get('objects'), list) and bool(safe_state.get('objects'))
        if normalized_variant == '3d':
            preview_3d = render_task_preview_3d(
                safe_state,
                task=task,
                team=team,
                request=request,
                canvas_width=frame_canvas_width or default_canvas_width,
                canvas_height=frame_canvas_height or default_canvas_height,
                pitch_orientation=orientation_key,
            )
            if preview_3d:
                return preview_3d
            return ''

        explicit_2d_url = render_task_preview_2d(
            safe_state,
            canvas_width=frame_canvas_width or default_canvas_width,
            canvas_height=frame_canvas_height or default_canvas_height,
            pitch_orientation=orientation_key,
            grass_style=_normalize_preview_grass_style(meta, '2d'),
        )
        if explicit_2d_url:
            return explicit_2d_url
        if has_objects:
            pitch_preset = str(meta.get('pitch_preset') or 'full_pitch').strip() or 'full_pitch'
            try:
                png_bytes = render_task_preview_png(
                    canvas_state=safe_state,
                    pitch_preset=pitch_preset,
                    pitch_orientation='portrait' if orientation_key == 'portrait' else 'landscape',
                    pitch_grass_style=_normalize_preview_grass_style(meta, '2d'),
                    world_width=frame_canvas_width,
                    world_height=frame_canvas_height,
                    max_side=2400,
                )
            except Exception:
                png_bytes = None
            if png_bytes:
                import base64

                return 'data:image/png;base64,' + base64.b64encode(png_bytes).decode('ascii')
        return preview_url if fallback_to_primary else ''

    def _frame_tokens_resolver(frame_state: Dict[str, Any]):
        return views._build_task_pdf_tokens_from_canvas_state(
            request,
            frame_state,
            canvas_width=frame_canvas_width,
            canvas_height=frame_canvas_height,
        )

    task_canvas_state: Dict[str, Any] = {}
    if isinstance(tactical_layout.get('objects'), list) and tactical_layout.get('objects'):
        task_canvas_state = {
            'version': str(tactical_layout.get('version') or '5.3.0'),
            'objects': tactical_layout.get('objects'),
        }
    if not isinstance(task_canvas_state.get('objects'), list) or not task_canvas_state.get('objects'):
        try:
            extracted_canvas_state, extracted_canvas_width, extracted_canvas_height = extract_task_canvas_state(task)
        except Exception:
            extracted_canvas_state, extracted_canvas_width, extracted_canvas_height = {}, 0, 0
    if isinstance(extracted_canvas_state, dict) and isinstance(extracted_canvas_state.get('objects'), list) and extracted_canvas_state.get('objects'):
        task_canvas_state = extracted_canvas_state
        if extracted_canvas_width:
            frame_canvas_width = extracted_canvas_width
        if extracted_canvas_height:
            frame_canvas_height = extracted_canvas_height

    raw_simulation = task_canvas_state.get('simulation') if isinstance(task_canvas_state.get('simulation'), dict) else {}
    raw_simulation_pro = raw_simulation.get('pro') if isinstance(raw_simulation.get('pro'), dict) else {}

    task_preview_2d_url = _resolve_task_preview_image_url(task, prefer_file_url=prefer_file_urls)
    if not task_preview_2d_url:
        generated_task_preview_2d_url = _render_variant_preview_url(task_canvas_state, '2d', fallback_to_primary=False)
        if generated_task_preview_2d_url:
            persisted_task_preview_2d_url = _persist_generated_task_preview_image(task, generated_task_preview_2d_url)
            task_preview_2d_url = persisted_task_preview_2d_url or generated_task_preview_2d_url
            if prefer_file_urls and getattr(task, 'task_preview_image', None):
                task_preview_2d_url = _resolve_task_preview_image_url(task, prefer_file_url=True) or task_preview_2d_url
    if not task_preview_2d_url:
        task_preview_2d_url = preview_url

    task_preview_3d_url = _render_variant_preview_url(task_canvas_state, '3d') if include_3d_snapshot else ''
    task_preview_3d_url = task_preview_3d_url or ''
    task_preview_3d_embed_url = build_task_preview_3d_embed_url(task, pitch_orientation=orientation_key) if (live_preview_mode or force_3d_embed_url) else ''

    def _frame_preview_resolver(frame_state: Dict[str, Any], variant: str) -> str:
        return _render_variant_preview_url(frame_state, variant, fallback_to_primary=False)

    animation_frame_cards = []
    if include_animation_cards:
        animation_frame_cards = build_animation_frame_cards(
            animation_frames,
            task=task,
            live_preview_mode=(live_preview_mode or force_3d_embed_url),
            pitch_orientation=orientation_key,
            frame_preview_resolver=_frame_preview_resolver,
            frame_tokens_resolver=_frame_tokens_resolver,
        )
    animation_object_tracks = build_animation_object_tracks_from_simulation_pro(raw_simulation_pro)
    if not animation_object_tracks:
        animation_object_tracks = build_animation_object_tracks(animation_frames)
    animation_object_summary = summarize_animation_object_tracks(animation_object_tracks)

    if not animation_frame_cards and (task_preview_2d_url or task_preview_3d_url):
        animation_frame_cards = [
            {
                'title': 'Situación base',
                'duration': 0,
                'preview_url': task_preview_2d_url or task_preview_3d_url,
                'preview_2d_url': task_preview_2d_url,
                'preview_3d_url': task_preview_3d_url,
                'preview_3d_embed_url': task_preview_3d_embed_url,
                'tokens': [],
                'is_fallback': True,
            }
        ]

    graphic_view_2d_url = task_preview_2d_url or ''
    graphic_view_3d_url = task_preview_3d_url or ''
    graphic_view_3d_embed_url = task_preview_3d_embed_url or ''
    first_real_animation_frame = _first_distinct_animation_frame(
        animation_frame_cards,
        base_preview_2d_url=graphic_view_2d_url,
        base_preview_3d_url=graphic_view_3d_url,
    )
    recreation_2d_url = str(first_real_animation_frame.get('preview_2d_url') or '').strip()
    if recreation_2d_url == graphic_view_2d_url:
        recreation_2d_url = ''
    recreation_3d_url = str(first_real_animation_frame.get('preview_3d_url') or '').strip()
    if recreation_3d_url == graphic_view_3d_url:
        recreation_3d_url = ''
    recreation_3d_embed_url = str(first_real_animation_frame.get('preview_3d_embed_url') or '').strip()

    return {
        'animation_frames': animation_frames,
        'animation_frame_cards': animation_frame_cards,
        'animation_object_tracks': animation_object_tracks,
        'animation_track_count': int(animation_object_summary.get('track_count') or 0),
        'animation_keyframe_count': int(animation_object_summary.get('keyframe_count') or 0),
        'animation_moving_track_count': int(animation_object_summary.get('moving_track_count') or 0),
        'task_preview_2d_url': task_preview_2d_url or preview_url,
        'task_preview_3d_url': task_preview_3d_url,
        'task_preview_3d_embed_url': task_preview_3d_embed_url,
        'graphic_view_2d_url': graphic_view_2d_url,
        'graphic_view_3d_url': graphic_view_3d_url,
        'graphic_view_3d_embed_url': graphic_view_3d_embed_url,
        'recreation_2d_url': recreation_2d_url,
        'recreation_3d_url': recreation_3d_url,
        'recreation_3d_embed_url': recreation_3d_embed_url,
    }
