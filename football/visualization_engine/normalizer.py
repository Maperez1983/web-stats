from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .scene_graph import make_field, make_node, make_scene_graph


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _normalize_kind(obj: Dict[str, Any]) -> Tuple[str, str]:
    explicit_kind = str(((obj.get('data') or {}).get('kind') if isinstance(obj.get('data'), dict) else '') or obj.get('kind') or '').strip().lower()
    label = str(obj.get('text') or obj.get('label') or '').strip().lower()
    obj_type = str(obj.get('type') or '').strip().lower()

    if explicit_kind in {'player_local', 'player_rival', 'player', 'token'}:
        return 'player', 'PlayerNode'
    if explicit_kind in {'goalkeeper_local', 'goalkeeper_rival', 'goalkeeper', 'gk'}:
        return 'goalkeeper', 'GoalkeeperNode'
    if explicit_kind in {'ball'}:
        return 'ball', 'BallNode'
    if explicit_kind in {'cone', 'disc_cone'}:
        return 'cone', 'ConeNode'
    if explicit_kind in {'arrow', 'curve_arrow', 'movement_line', 'pass_arrow', 'line'}:
        return 'arrow', 'ArrowNode'
    if explicit_kind in {'zone', 'space_zone', 'surface_area', 'shape_rect', 'shape_ellipse', 'spotlight'}:
        return 'zone', 'ZoneNode'
    if explicit_kind in {'text', 'label'}:
        return 'text', 'TextNode'
    if explicit_kind in {'goal', 'goal_frame', 'goal_post'}:
        return 'goal', 'GoalNode'
    if explicit_kind in {'pole', 'pike', 'pica'}:
        return 'pole', 'PoleNode'

    if obj_type == 'line':
        return 'arrow', 'ArrowNode'
    if obj_type == 'textbox' or obj_type == 'text':
        return 'text', 'TextNode'
    if obj_type == 'circle':
        if 'portero' in label or 'gk' in label:
            return 'goalkeeper', 'GoalkeeperNode'
        if 'bal' in label:
            return 'ball', 'BallNode'
        return 'player', 'PlayerNode'
    if obj_type == 'rect':
        if label:
            return 'text', 'TextNode'
        return 'zone', 'ZoneNode'
    if obj_type == 'group':
        if 'goalkeeper' in explicit_kind or 'portero' in label:
            return 'goalkeeper', 'GoalkeeperNode'
        if 'player' in explicit_kind or 'jugador' in label or 'token' in explicit_kind:
            return 'player', 'PlayerNode'

    return 'unknown', 'UnknownNode'


def _normalize_style(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'fill': obj.get('fill'),
        'stroke': obj.get('stroke'),
        'stroke_width': _parse_float(obj.get('strokeWidth')),
        'opacity': _parse_float(obj.get('opacity'), 1.0) or 1.0,
        'scale_x': _parse_float(obj.get('scaleX'), 1.0) or 1.0,
        'scale_y': _parse_float(obj.get('scaleY'), 1.0) or 1.0,
    }


def _normalize_points(obj: Dict[str, Any], *, canvas_width: int, canvas_height: int) -> List[Dict[str, float]]:
    raw_points = obj.get('points') if isinstance(obj.get('points'), list) else []
    normalized: List[Dict[str, float]] = []
    safe_width = max(1, int(canvas_width or 1))
    safe_height = max(1, int(canvas_height or 1))
    for point in raw_points:
        if not isinstance(point, dict):
            continue
        normalized.append(
            {
                'x': max(0.0, min(1.0, _parse_float(point.get('x')) / safe_width)),
                'y': max(0.0, min(1.0, _parse_float(point.get('y')) / safe_height)),
            }
        )
    return normalized


def _normalize_text(obj: Dict[str, Any]) -> str:
    return str(obj.get('text') or obj.get('label') or '').strip()


def _normalize_object(obj: Dict[str, Any], *, index: int, canvas_width: int, canvas_height: int, warnings: List[str]) -> Dict[str, Any]:
    safe_width = max(1, int(canvas_width or 1))
    safe_height = max(1, int(canvas_height or 1))
    kind, node_type = _normalize_kind(obj)
    left = _parse_float(obj.get('left'))
    top = _parse_float(obj.get('top'))
    width = _parse_float(obj.get('width'))
    height = _parse_float(obj.get('height'))
    radius = _parse_float(obj.get('radius'))
    rotation = _parse_float(obj.get('angle'))
    scale_x = _parse_float(obj.get('scaleX'), 1.0) or 1.0
    scale_y = _parse_float(obj.get('scaleY'), 1.0) or 1.0
    center_x = left
    center_y = top

    if str(obj.get('type') or '').strip().lower() == 'rect':
        center_x = left + ((width * scale_x) / 2.0)
        center_y = top + ((height * scale_y) / 2.0)

    semantic_role = kind
    if kind == 'unknown':
        warnings.append(f'Objeto #{index + 1} no reconocido; se normaliza como UnknownNode.')

    return make_node(
        f'obj-{index + 1}',
        kind=kind,
        node_type=node_type,
        x=max(0.0, min(1.0, center_x / safe_width)),
        y=max(0.0, min(1.0, center_y / safe_height)),
        rotation=rotation,
        scale=max(scale_x, scale_y, 1.0),
        width=(width * scale_x) / safe_width,
        height=(height * scale_y) / safe_height,
        radius=radius / max(safe_width, safe_height),
        points=_normalize_points(obj, canvas_width=safe_width, canvas_height=safe_height),
        text=_normalize_text(obj),
        style=_normalize_style(obj),
        semantic_role=semantic_role,
        source_ref={'index': index, 'object_type': str(obj.get('type') or '').strip().lower()},
        raw_kind=str(((obj.get('data') or {}).get('kind') if isinstance(obj.get('data'), dict) else '') or obj.get('kind') or '').strip(),
    )


def build_scene_graph_from_canvas_state(canvas_state: Any, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    safe_state = canvas_state if isinstance(canvas_state, dict) else {}
    safe_meta = meta if isinstance(meta, dict) else {}
    warnings: List[str] = []
    canvas_width = _parse_int(safe_state.get('width') or safe_meta.get('canvas_width') or ((safe_meta.get('graphic_editor') or {}).get('canvas_width') if isinstance(safe_meta.get('graphic_editor'), dict) else 0), 1054)
    canvas_height = _parse_int(safe_state.get('height') or safe_meta.get('canvas_height') or ((safe_meta.get('graphic_editor') or {}).get('canvas_height') if isinstance(safe_meta.get('graphic_editor'), dict) else 0), 684)
    objects = safe_state.get('objects') if isinstance(safe_state.get('objects'), list) else []
    normalized_objects = [
        _normalize_object(obj, index=index, canvas_width=canvas_width, canvas_height=canvas_height, warnings=warnings)
        for index, obj in enumerate(objects)
        if isinstance(obj, dict)
    ]

    field = make_field(
        orientation=str(safe_meta.get('pitch_orientation') or 'landscape').strip().lower() or 'landscape',
        width=canvas_width,
        height=canvas_height,
        preset=str(safe_meta.get('pitch_preset') or 'full_pitch').strip() or 'full_pitch',
        grass_style=str(safe_meta.get('pitch_grass_style') or 'broadcast_premium').strip().lower() or 'broadcast_premium',
    )
    metadata = {
        'source': 'canvas_state',
        'canvas_version': str(safe_state.get('version') or '5.3.0'),
        'object_count': len(normalized_objects),
    }
    return make_scene_graph(field=field, objects=normalized_objects, timeline=[], metadata=metadata, warnings=warnings)


def build_scene_graph_from_tactical_layout(tactical_layout: Any) -> Dict[str, Any]:
    safe_layout = tactical_layout if isinstance(tactical_layout, dict) else {}
    meta = safe_layout.get('meta') if isinstance(safe_layout.get('meta'), dict) else {}
    canvas_state = {
        'version': str(safe_layout.get('version') or '5.3.0'),
        'width': _parse_int(((meta.get('graphic_editor') or {}).get('canvas_width') if isinstance(meta.get('graphic_editor'), dict) else 0), 1054),
        'height': _parse_int(((meta.get('graphic_editor') or {}).get('canvas_height') if isinstance(meta.get('graphic_editor'), dict) else 0), 684),
        'objects': safe_layout.get('objects') if isinstance(safe_layout.get('objects'), list) else [],
    }
    scene_graph = build_scene_graph_from_canvas_state(canvas_state, meta=meta)
    warnings = list(scene_graph.get('warnings') or [])
    normalized_timeline: List[Dict[str, Any]] = []
    raw_timeline = safe_layout.get('timeline') if isinstance(safe_layout.get('timeline'), list) else []
    for index, frame in enumerate(raw_timeline[:24]):
        if not isinstance(frame, dict):
            continue
        frame_state = frame.get('canvas_state') if isinstance(frame.get('canvas_state'), dict) else {}
        frame_graph = build_scene_graph_from_canvas_state(frame_state, meta=meta)
        normalized_timeline.append(
            {
                'index': index,
                'title': str(frame.get('title') or f'Paso {index + 1}').strip() or f'Paso {index + 1}',
                'duration': max(1, min(_parse_int(frame.get('duration'), 3), 20)),
                'objects': frame_graph.get('objects') or [],
                'warnings': frame_graph.get('warnings') or [],
            }
        )
        for warning in frame_graph.get('warnings') or []:
            warnings.append(f'Frame {index + 1}: {warning}')

    metadata = dict(scene_graph.get('metadata') or {})
    metadata.update(
        {
            'source': 'tactical_layout',
            'timeline_frames': len(normalized_timeline),
        }
    )
    return make_scene_graph(
        field=scene_graph.get('field') or {},
        objects=scene_graph.get('objects') or [],
        timeline=normalized_timeline,
        metadata=metadata,
        warnings=warnings,
    )


def scene_graph_diagnostic_payload(scene_graph: Dict[str, Any]) -> Dict[str, Any]:
    objects = scene_graph.get('objects') if isinstance(scene_graph.get('objects'), list) else []
    timeline = scene_graph.get('timeline') if isinstance(scene_graph.get('timeline'), list) else []
    return {
        'field': scene_graph.get('field') or {},
        'metadata': scene_graph.get('metadata') or {},
        'warnings': scene_graph.get('warnings') or [],
        'object_count': len(objects),
        'timeline_count': len(timeline),
        'object_kinds': [str(obj.get('kind') or 'unknown') for obj in objects[:80] if isinstance(obj, dict)],
        'timeline_titles': [str(frame.get('title') or '') for frame in timeline[:24] if isinstance(frame, dict)],
    }
