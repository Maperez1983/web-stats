from __future__ import annotations

import base64
import os
from typing import Any, Dict
from urllib.parse import quote

from django.templatetags.static import static

from ..preview_render import render_task_detail_3d_scene_png


def _pdf_3d_camera_preset(pitch_orientation: str) -> str:
    return 'coach' if str(pitch_orientation or '').strip().lower() == 'portrait' else 'analyst'


def _build_pitch3d_context_payload(team: Any, request: Any) -> Dict[str, Any]:
    from .. import views

    static_build_id = views._resolve_static_build_id()
    pitch3d_player_model_src = ''
    try:
        pitch3d_player_model_url = str(os.getenv('TASK_PLAYER_MODEL_URL') or '').strip()
        pitch3d_player_model_static_path = str(os.getenv('TASK_PLAYER_MODEL_STATIC_PATH') or '').strip()
        if pitch3d_player_model_url:
            pitch3d_player_model_src = pitch3d_player_model_url
        elif pitch3d_player_model_static_path:
            pitch3d_player_model_src = static(pitch3d_player_model_static_path.lstrip('/'))
            if static_build_id:
                pitch3d_player_model_src = f"{pitch3d_player_model_src}?v={quote(str(static_build_id))}"
    except Exception:
        pitch3d_player_model_src = ''
    pitch3d_assets = views._task_pitch3d_asset_context(static_build_id, player_model_src=pitch3d_player_model_src)

    stadium_palette = {'primary': '#047857', 'secondary': '#f8fafc', 'accent': '#073b32'}
    stadium_ads = {
        'top': str(getattr(team, 'display_name', '') or getattr(team, 'name', '') or 'Club').strip() or 'Club',
        'right': '2J Football Intelligence',
        'bottom': str(getattr(team, 'display_name', '') or getattr(team, 'name', '') or 'Club').strip() or 'Club',
        'left': 'Partner',
    }
    workspace = None
    try:
        workspace = views._get_active_workspace(request)
    except Exception:
        workspace = None
    if not workspace and team:
        try:
            workspace = views.Workspace.objects.filter(primary_team=team).first()
        except Exception:
            workspace = None
    try:
        if team:
            stadium_palette = views._team_stadium_palette(workspace, team)
            ads = views._team_stadium_ads(workspace, team)
            if isinstance(ads, dict):
                stadium_ads.update({
                    'top': str(ads.get('top') or stadium_ads['top']).strip() or stadium_ads['top'],
                    'right': str(ads.get('right') or stadium_ads['right']).strip() or stadium_ads['right'],
                    'bottom': str(ads.get('bottom') or stadium_ads['bottom']).strip() or stadium_ads['bottom'],
                    'left': str(ads.get('left') or stadium_ads['left']).strip() or stadium_ads['left'],
                })
    except Exception:
        pass
    return {
        'pitch3d_assets': pitch3d_assets,
        'pitch3d_context_payload': {
            'teamName': str(getattr(team, 'display_name', '') or getattr(team, 'name', '') or '').strip(),
            'stadiumPalette': stadium_palette,
            'stadiumAds': stadium_ads,
        },
    }


def render_task_preview_3d(
    canvas_state: Dict[str, Any],
    *,
    task: Any,
    team: Any,
    request: Any,
    canvas_width: int,
    canvas_height: int,
    pitch_orientation: str,
) -> str:
    safe_state = canvas_state if isinstance(canvas_state, dict) else {}
    payload = _build_pitch3d_context_payload(team, request)
    snapshot_state = {
        'version': str(safe_state.get('version') or '5.3.0'),
        'objects': list(safe_state.get('objects') or []),
        'canvas_width': canvas_width,
        'canvas_height': canvas_height,
    }
    snapshot_frames = [{
        'title': str(getattr(task, 'title', '') or '').strip() or 'Situación base',
        'duration': 4,
        'canvas_state': snapshot_state,
    }]
    try:
        png_bytes = render_task_detail_3d_scene_png(
            task_title=str(getattr(task, 'title', '') or '').strip(),
            stadium_model_url=payload['pitch3d_assets'].get('pitch3d_stadium_model_src') or '',
            stadium_top_h_url=payload['pitch3d_assets'].get('pitch3d_stadium_top_h_src') or '',
            stadium_top_v_url=payload['pitch3d_assets'].get('pitch3d_stadium_top_v_src') or '',
            stadium_overlay_h_url=payload['pitch3d_assets'].get('pitch3d_stadium_overlay_h_src') or '',
            stadium_overlay_v_url=payload['pitch3d_assets'].get('pitch3d_stadium_overlay_v_src') or '',
            player_model_url=payload['pitch3d_assets'].get('pitch3d_player_model_src') or '',
            pitch3d_context=payload['pitch3d_context_payload'],
            graphic_editor_state=snapshot_state,
            animation_frames=snapshot_frames,
            pitch_orientation=pitch_orientation,
            camera_preset=_pdf_3d_camera_preset(pitch_orientation),
            viewport_width=1200 if pitch_orientation == 'portrait' else 1500,
            viewport_height=1800 if pitch_orientation == 'portrait' else 1100,
            device_scale_factor=2.0,
            timeout_ms=35000,
        )
    except Exception:
        png_bytes = None
    if png_bytes:
        return 'data:image/png;base64,' + base64.b64encode(png_bytes).decode('ascii')
    return ''


def build_task_preview_3d_embed_url(task: Any, *, frame: int | None = None, pitch_orientation: str = 'landscape') -> str:
    from django.urls import reverse

    if not getattr(task, 'id', None):
        return ''
    try:
        camera = _pdf_3d_camera_preset(pitch_orientation)
        suffix = f'?camera={camera}'
        if frame:
            suffix = f'?frame={int(frame)}&camera={camera}'
        return reverse('session-task-pdf-3d-embed', args=[int(task.id)]) + suffix
    except Exception:
        return ''
