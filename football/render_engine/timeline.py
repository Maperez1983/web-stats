from __future__ import annotations

import math
from typing import Any, Callable, Dict, List


def _safe_text(value: Any) -> str:
    return str(value or '').strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _resolve_track_uid(obj: Dict[str, Any], index: int) -> str:
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    candidates = [
        _safe_text(data.get('layer_uid')),
        _safe_text(data.get('uid')),
        _safe_text(data.get('playerId')),
        _safe_text(data.get('object_id')),
        _safe_text(obj.get('id')),
        _safe_text(obj.get('name')),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    kind = _safe_text(data.get('kind')) or _safe_text(obj.get('type')) or 'object'
    return f'{kind}:{int(index)}'


def _resolve_track_label(obj: Dict[str, Any], fallback_uid: str) -> str:
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    for candidate in (
        data.get('label'),
        data.get('title'),
        data.get('name'),
        obj.get('text'),
        obj.get('name'),
    ):
        text = _safe_text(candidate)
        if text:
            return text[:80]
    return fallback_uid[:80]


def _resolve_track_kind(obj: Dict[str, Any]) -> str:
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    return _safe_text(data.get('kind')) or _safe_text(obj.get('type')) or 'object'


def build_animation_object_tracks(animation_frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tracks_map: Dict[str, Dict[str, Any]] = {}
    for frame_index, frame in enumerate(animation_frames):
        if not isinstance(frame, dict):
            continue
        frame_state = frame.get('canvas_state') if isinstance(frame.get('canvas_state'), dict) else {}
        objects = frame_state.get('objects') if isinstance(frame_state.get('objects'), list) else []
        for object_index, obj in enumerate(objects):
            if not isinstance(obj, dict):
                continue
            uid = _resolve_track_uid(obj, object_index)
            label = _resolve_track_label(obj, uid)
            kind = _resolve_track_kind(obj)
            left = _safe_float(obj.get('left'))
            top = _safe_float(obj.get('top'))
            angle = _safe_float(obj.get('angle'))
            scale_x = _safe_float(obj.get('scaleX') or 1)
            scale_y = _safe_float(obj.get('scaleY') or 1)
            opacity = _safe_float(obj.get('opacity') if obj.get('opacity') is not None else 1)
            track = tracks_map.setdefault(
                uid,
                {
                    'uid': uid,
                    'label': label,
                    'kind': kind,
                    'keyframes': [],
                    'distance': 0.0,
                    'moving': False,
                },
            )
            if not track.get('label'):
                track['label'] = label
            if not track.get('kind'):
                track['kind'] = kind
            previous = track['keyframes'][-1] if track['keyframes'] else None
            if previous:
                delta = math.hypot(left - _safe_float(previous.get('left')), top - _safe_float(previous.get('top')))
                if delta > 0.01:
                    track['distance'] = round(_safe_float(track.get('distance')) + delta, 2)
                    track['moving'] = True
            track['keyframes'].append(
                {
                    'step_index': int(frame_index),
                    'step_number': int(frame_index) + 1,
                    'title': _safe_text(frame.get('title')) or f'Paso {frame_index + 1}',
                    'duration': max(1, _safe_int(frame.get('duration')) or 3),
                    'left': round(left, 2),
                    'top': round(top, 2),
                    'angle': round(angle, 2),
                    'scale_x': round(scale_x, 3),
                    'scale_y': round(scale_y, 3),
                    'opacity': round(opacity, 3),
                }
            )
    tracks: List[Dict[str, Any]] = []
    for track in tracks_map.values():
        keyframes = track.get('keyframes') if isinstance(track.get('keyframes'), list) else []
        if not keyframes:
            continue
        first = keyframes[0]
        last = keyframes[-1]
        tracks.append(
            {
                'uid': track.get('uid'),
                'label': track.get('label'),
                'kind': track.get('kind'),
                'keyframes': keyframes,
                'keyframe_count': len(keyframes),
                'first_step': first.get('step_number'),
                'last_step': last.get('step_number'),
                'distance': round(_safe_float(track.get('distance')), 2),
                'moving': bool(track.get('moving')),
            }
        )
    tracks.sort(key=lambda item: (-int(item.get('keyframe_count') or 0), str(item.get('label') or '').lower(), str(item.get('uid') or '').lower()))
    return tracks


def summarize_animation_object_tracks(animation_tracks: List[Dict[str, Any]]) -> Dict[str, int]:
    track_count = len(animation_tracks)
    keyframe_count = sum(int(track.get('keyframe_count') or 0) for track in animation_tracks if isinstance(track, dict))
    moving_track_count = sum(1 for track in animation_tracks if isinstance(track, dict) and track.get('moving'))
    return {
        'track_count': int(track_count),
        'keyframe_count': int(keyframe_count),
        'moving_track_count': int(moving_track_count),
    }


def build_animation_object_tracks_from_simulation_pro(raw_pro: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_pro, dict):
        return []
    raw_tracks = raw_pro.get('tracks') if isinstance(raw_pro.get('tracks'), dict) else {}
    tracks: List[Dict[str, Any]] = []
    for uid, raw_keyframes in list(raw_tracks.items())[:240]:
        safe_uid = _safe_text(uid)
        if not safe_uid or not isinstance(raw_keyframes, list):
            continue
        keyframes: List[Dict[str, Any]] = []
        distance = 0.0
        previous = None
        for index, raw_kf in enumerate(raw_keyframes[:240]):
            if not isinstance(raw_kf, dict):
                continue
            props = raw_kf.get('props') if isinstance(raw_kf.get('props'), dict) else {}
            if not props:
                continue
            current = {
                'step_index': int(index),
                'step_number': int(index) + 1,
                'title': f'KF {index + 1}',
                'duration': 0,
                't_ms': max(0, _safe_int(raw_kf.get('t_ms'))),
                'easing': _safe_text(raw_kf.get('easing')) or 'ease',
                'left': round(_safe_float(props.get('left')), 2),
                'top': round(_safe_float(props.get('top')), 2),
                'angle': round(_safe_float(props.get('angle')), 2),
                'scale_x': round(_safe_float(props.get('scaleX') or 1), 3),
                'scale_y': round(_safe_float(props.get('scaleY') or 1), 3),
                'opacity': round(_safe_float(props.get('opacity') if props.get('opacity') is not None else 1), 3),
            }
            if previous:
                distance += math.hypot(current['left'] - previous['left'], current['top'] - previous['top'])
            previous = current
            keyframes.append(current)
        if not keyframes:
            continue
        moving = round(distance, 2) > 0
        tracks.append(
            {
                'uid': safe_uid,
                'label': safe_uid[:80],
                'kind': 'track',
                'keyframes': keyframes,
                'keyframe_count': len(keyframes),
                'first_step': 1,
                'last_step': len(keyframes),
                'distance': round(distance, 2),
                'moving': moving,
            }
        )
    tracks.sort(key=lambda item: (-int(item.get('keyframe_count') or 0), str(item.get('uid') or '').lower()))
    return tracks


def build_animation_frame_cards(
    animation_frames: List[Dict[str, Any]],
    *,
    task: Any,
    live_preview_mode: bool,
    pitch_orientation: str,
    frame_preview_resolver: Callable[[Dict[str, Any], str], str],
    frame_tokens_resolver: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    from .normalizer import parse_int
    from .renderer_3d import build_task_preview_3d_embed_url

    cards: List[Dict[str, Any]] = []
    for index, frame in enumerate(animation_frames):
        frame_state = frame.get('canvas_state')
        frame_preview_2d_url = frame_preview_resolver(frame_state, '2d')
        frame_preview_3d_url = frame_preview_resolver(frame_state, '3d')
        frame_preview_3d_embed_url = ''
        if live_preview_mode:
            frame_preview_3d_embed_url = build_task_preview_3d_embed_url(
                task,
                frame=index + 1,
                pitch_orientation=pitch_orientation,
            )
        cards.append(
            {
                'title': str(frame.get('title') or f'Paso {index + 1}').strip() or f'Paso {index + 1}',
                'duration': max(1, min(parse_int(frame.get('duration')) or 3, 20)),
                'preview_url': frame_preview_2d_url or frame_preview_3d_url,
                'preview_2d_url': frame_preview_2d_url,
                'preview_3d_url': frame_preview_3d_url,
                'preview_3d_embed_url': frame_preview_3d_embed_url,
                'tokens': frame_tokens_resolver(frame_state),
            }
        )
    return cards


def first_real_frame_card(animation_frame_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    for frame_card in animation_frame_cards:
        if isinstance(frame_card, dict) and not frame_card.get('is_fallback'):
            return frame_card
    return {}
