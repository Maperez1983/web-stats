from __future__ import annotations

from typing import Dict, Iterable, List


def normalize_point(x: float, y: float) -> Dict[str, float]:
    return {
        'x': max(0.0, min(1.0, float(x or 0.0))),
        'y': max(0.0, min(1.0, float(y or 0.0))),
    }


def normalized_to_canvas(point: Dict[str, float], width: int, height: int) -> Dict[str, float]:
    return {
        'x': float(point.get('x') or 0.0) * max(1, int(width or 1)),
        'y': float(point.get('y') or 0.0) * max(1, int(height or 1)),
    }


def normalized_to_world(point: Dict[str, float], *, field_width: float = 105.0, field_height: float = 68.0) -> Dict[str, float]:
    return {
        'x': float(point.get('x') or 0.0) * field_width,
        'y': float(point.get('y') or 0.0) * field_height,
        'z': float(point.get('z') or 0.0),
    }


def points_bounds(points: Iterable[Dict[str, float]]) -> Dict[str, float]:
    safe_points: List[Dict[str, float]] = [point for point in points if isinstance(point, dict)]
    if not safe_points:
        return {'x': 0.0, 'y': 0.0, 'width': 0.0, 'height': 0.0}
    xs = [float(point.get('x') or 0.0) for point in safe_points]
    ys = [float(point.get('y') or 0.0) for point in safe_points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return {'x': min_x, 'y': min_y, 'width': max_x - min_x, 'height': max_y - min_y}
