from __future__ import annotations

from typing import Any, Dict, List


def make_field(*, orientation: str = 'landscape', width: int = 1054, height: int = 684, preset: str = 'full_pitch', grass_style: str = 'broadcast_premium') -> Dict[str, Any]:
    return {
        'orientation': str(orientation or 'landscape').strip().lower() or 'landscape',
        'canvas_width': max(1, int(width or 1054)),
        'canvas_height': max(1, int(height or 684)),
        'preset': str(preset or 'full_pitch').strip() or 'full_pitch',
        'grass_style': str(grass_style or 'broadcast_premium').strip().lower() or 'broadcast_premium',
    }


def make_node(
    node_id: str,
    *,
    kind: str,
    node_type: str,
    x: float,
    y: float,
    z: float = 0.0,
    rotation: float = 0.0,
    scale: float = 1.0,
    width: float = 0.0,
    height: float = 0.0,
    radius: float = 0.0,
    points: List[Dict[str, float]] | None = None,
    text: str = '',
    style: Dict[str, Any] | None = None,
    semantic_role: str = '',
    source_ref: Dict[str, Any] | None = None,
    raw_kind: str = '',
) -> Dict[str, Any]:
    return {
        'id': str(node_id or '').strip() or 'node',
        'kind': str(kind or 'unknown').strip().lower() or 'unknown',
        'type': str(node_type or 'UnknownNode').strip() or 'UnknownNode',
        'position': {'x': float(x or 0.0), 'y': float(y or 0.0), 'z': float(z or 0.0)},
        'rotation': float(rotation or 0.0),
        'scale': float(scale or 1.0),
        'size': {
            'width': float(width or 0.0),
            'height': float(height or 0.0),
            'radius': float(radius or 0.0),
        },
        'points': list(points or []),
        'text': str(text or ''),
        'style': dict(style or {}),
        'semantic_role': str(semantic_role or '').strip(),
        'raw_kind': str(raw_kind or '').strip(),
        'source_ref': dict(source_ref or {}),
    }


def make_scene_graph(
    *,
    field: Dict[str, Any],
    objects: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        'field': field,
        'objects': list(objects or []),
        'timeline': list(timeline or []),
        'metadata': dict(metadata or {}),
        'warnings': list(warnings or []),
    }
