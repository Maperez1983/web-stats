from __future__ import annotations

from typing import Any, Dict, List


def classify_arrow_action(
    arrow_node: Dict[str, Any],
    *,
    nearest_start_entity: Dict[str, Any] | None = None,
    nearest_end_entity: Dict[str, Any] | None = None,
    ball_owner_id: str | None = None,
) -> str:
    style = arrow_node.get('style') if isinstance(arrow_node.get('style'), dict) else {}
    stroke = str(style.get('stroke') or '').strip().lower()
    width = float(style.get('stroke_width') or 0.0)
    points = arrow_node.get('points') if isinstance(arrow_node.get('points'), list) else []
    point_count = len(points)

    start_role = str((nearest_start_entity or {}).get('semantic_role') or '')
    end_role = str((nearest_end_entity or {}).get('semantic_role') or '')
    start_id = str((nearest_start_entity or {}).get('id') or '')

    if stroke in {'#ef4444', '#dc2626', '#b91c1c'}:
        return 'pressure'
    if stroke in {'#22c55e', '#16a34a', '#84cc16'}:
        return 'support'
    if stroke in {'#3b82f6', '#2563eb'}:
        return 'cover'
    if ball_owner_id and start_id and ball_owner_id == start_id and end_role in {'player', 'goalkeeper', 'neutral'}:
        return 'pass'
    if point_count >= 2 and width >= 4 and start_role in {'player', 'goalkeeper', 'neutral'} and end_role in {'player', 'goalkeeper', 'neutral'}:
        return 'pass'
    if point_count >= 2 and start_role in {'player', 'goalkeeper', 'neutral'} and ball_owner_id and start_id == ball_owner_id:
        return 'dribble'
    if start_role in {'player', 'goalkeeper', 'neutral', 'opponent'}:
        return 'run'
    return 'unknown_action'


def classify_zone_semantics(zone_node: Dict[str, Any]) -> str:
    text = str(zone_node.get('text') or '').strip().lower()
    style = zone_node.get('style') if isinstance(zone_node.get('style'), dict) else {}
    fill = str(style.get('fill') or '').strip().lower()
    stroke = str(style.get('stroke') or '').strip().lower()

    if any(token in text for token in {'pres', 'pressure', 'pressing'}):
        return 'pressing_zone'
    if any(token in text for token in {'finish', 'final', 'remate'}):
        return 'finishing_zone'
    if any(token in text for token in {'build', 'inicio', 'salida'}):
        return 'build_up_zone'
    if any(token in text for token in {'occup', 'ocupa', 'support', 'apoyo'}):
        return 'occupation_zone'

    if fill in {'#22c55e', '#16a34a', '#84cc16'} or stroke in {'#22c55e', '#16a34a', '#84cc16'}:
        return 'occupation_zone'
    if fill in {'#ef4444', '#dc2626', '#b91c1c'} or stroke in {'#ef4444', '#dc2626', '#b91c1c'}:
        return 'pressing_zone'
    if fill in {'#facc15', '#eab308'} or stroke in {'#facc15', '#eab308'}:
        return 'finishing_zone'
    if fill in {'#3b82f6', '#2563eb'} or stroke in {'#3b82f6', '#2563eb'}:
        return 'build_up_zone'
    return 'unknown_zone'


def summarize_timeline_movements(prev_entities: List[Dict[str, Any]], curr_entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    prev_map = {str(entity.get('id') or ''): entity for entity in prev_entities if isinstance(entity, dict)}
    curr_map = {str(entity.get('id') or ''): entity for entity in curr_entities if isinstance(entity, dict)}
    moved: List[Dict[str, Any]] = []
    for entity_id, curr in curr_map.items():
        prev = prev_map.get(entity_id)
        if not prev:
            continue
        prev_pos = prev.get('position') if isinstance(prev.get('position'), dict) else {}
        curr_pos = curr.get('position') if isinstance(curr.get('position'), dict) else {}
        dx = float(curr_pos.get('x') or 0.0) - float(prev_pos.get('x') or 0.0)
        dy = float(curr_pos.get('y') or 0.0) - float(prev_pos.get('y') or 0.0)
        distance = (dx ** 2 + dy ** 2) ** 0.5
        if distance <= 0.0001:
            continue
        direction_x = 'right' if dx > 0.0001 else ('left' if dx < -0.0001 else 'center')
        direction_y = 'down' if dy > 0.0001 else ('up' if dy < -0.0001 else 'center')
        moved.append(
            {
                'entity_id': entity_id,
                'kind': curr.get('kind'),
                'semantic_role': curr.get('semantic_role'),
                'distance': round(distance, 6),
                'direction': {'x': direction_x, 'y': direction_y},
            }
        )
    return {'moved_entities': moved}


__all__ = [
    'classify_arrow_action',
    'classify_zone_semantics',
    'summarize_timeline_movements',
]
