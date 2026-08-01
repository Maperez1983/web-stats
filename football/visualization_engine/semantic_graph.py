from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .actions import classify_arrow_action, classify_zone_semantics, summarize_timeline_movements


def _safe_position(node: Dict[str, Any]) -> Dict[str, float]:
    position = node.get('position') if isinstance(node.get('position'), dict) else {}
    return {
        'x': float(position.get('x') or 0.0),
        'y': float(position.get('y') or 0.0),
        'z': float(position.get('z') or 0.0),
    }


def _distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    dx = float(a.get('x') or 0.0) - float(b.get('x') or 0.0)
    dy = float(a.get('y') or 0.0) - float(b.get('y') or 0.0)
    return (dx ** 2 + dy ** 2) ** 0.5


def _style_value(node: Dict[str, Any], key: str) -> str:
    style = node.get('style') if isinstance(node.get('style'), dict) else {}
    return str(style.get(key) or '').strip().lower()


def _infer_player_team(node: Dict[str, Any]) -> str:
    fill = _style_value(node, 'fill')
    if fill in {'#2563eb', '#1d4ed8', '#3b82f6'}:
        return 'home'
    if fill in {'#ef4444', '#dc2626', '#b91c1c'}:
        return 'away'
    if fill in {'#f97316', '#fb923c'}:
        return 'neutral'
    return 'unknown'


def _infer_player_role(node: Dict[str, Any], semantic_role: str) -> str:
    raw_kind = str(node.get('raw_kind') or '').strip().lower()
    text = str(node.get('text') or '').strip().lower()
    if semantic_role == 'goalkeeper' or raw_kind in {'goalkeeper', 'gk'} or text == 'gk':
        return 'goalkeeper'
    if semantic_role == 'coach':
        return 'coach'
    if any(token in text for token in {'def', 'cb', 'lb', 'rb'}):
        return 'defender'
    if any(token in text for token in {'mid', 'cm', 'dm', 'am'}):
        return 'midfielder'
    if any(token in text for token in {'fw', 'st', 'cf', 'wing'}):
        return 'forward'
    return 'outfield'


def _infer_body_orientation(node: Dict[str, Any]) -> float:
    rotation = float(node.get('rotation') or 0.0)
    if rotation:
        return rotation
    points = node.get('points') if isinstance(node.get('points'), list) else []
    if len(points) >= 2:
        start = points[0] if isinstance(points[0], dict) else {}
        end = points[-1] if isinstance(points[-1], dict) else {}
        dx = float(end.get('x') or 0.0) - float(start.get('x') or 0.0)
        dy = float(end.get('y') or 0.0) - float(start.get('y') or 0.0)
        if abs(dx) >= abs(dy):
            return 0.0 if dx >= 0 else 180.0
        return 90.0 if dy >= 0 else -90.0
    return 0.0


def _infer_circle_semantic_role(node: Dict[str, Any]) -> str:
    fill = _style_value(node, 'fill')
    radius = float(((node.get('size') or {}).get('radius')) or 0.0)
    if fill == '#ffffff' and radius <= 0.02:
        return 'ball'
    if fill in {'#f97316', '#fb923c'}:
        return 'goalkeeper'
    return 'player'


def _semantic_kind(node: Dict[str, Any]) -> str:
    kind = str(node.get('kind') or 'unknown')
    node_type = str(node.get('type') or '')
    fill = _style_value(node, 'fill')
    size = node.get('size') if isinstance(node.get('size'), dict) else {}
    width = float(size.get('width') or 0.0)
    height = float(size.get('height') or 0.0)
    text = str(node.get('text') or '').strip().lower()

    if kind == 'player' and node_type == 'PlayerNode':
        return _infer_circle_semantic_role(node)
    if kind == 'zone' and node_type == 'ZoneNode':
        if width <= 0.03 and height <= 0.03 and fill in {'#f97316', '#fb923c', '#f59e0b', '#facc15'}:
            return 'cone'
        if width <= 0.02 and height >= 0.05 and fill in {'#ef4444', '#dc2626', '#b91c1c'}:
            return 'pole'
    if kind == 'text' and any(token in text for token in {'coach', 'entrenador'}):
        return 'coach'
    return kind


def _node_number(node: Dict[str, Any]) -> str:
    text = str(node.get('text') or '').strip()
    if text.isdigit():
        return text
    source_ref = node.get('source_ref') if isinstance(node.get('source_ref'), dict) else {}
    index = source_ref.get('index')
    if isinstance(index, int):
        return str(index + 1)
    return ''


def _nearest_entity(position: Dict[str, float], entities: Iterable[Dict[str, Any]], *, allowed_roles: Iterable[str] | None = None) -> Tuple[Dict[str, Any] | None, float]:
    allowed = set(allowed_roles or [])
    best_entity = None
    best_distance = 999.0
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        role = str(entity.get('semantic_role') or '')
        if allowed and role not in allowed:
            continue
        distance = _distance(position, _safe_position(entity))
        if distance < best_distance:
            best_entity = entity
            best_distance = distance
    return best_entity, best_distance


def _build_entities(objects: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    for node in objects:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get('type') or '')
        kind = _semantic_kind(node)
        position = _safe_position(node)
        semantic_role = kind

        if kind == 'goalkeeper':
            semantic_role = 'goalkeeper'
        elif kind == 'player':
            team = _infer_player_team(node)
            semantic_role = 'opponent' if team == 'away' else ('neutral' if team == 'neutral' else 'player')
        elif kind == 'coach':
            semantic_role = 'coach'
        elif kind == 'text':
            semantic_role = 'text'
        elif kind == 'zone':
            semantic_role = 'zone'
        elif kind == 'arrow':
            semantic_role = 'arrow'
        elif kind == 'ball':
            semantic_role = 'ball'
        elif kind == 'unknown':
            semantic_role = 'unknown'

        entity = {
            'id': str(node.get('id') or 'entity'),
            'kind': kind,
            'node_type': node_type,
            'semantic_role': semantic_role,
            'position': position,
            'rotation': float(node.get('rotation') or 0.0),
            'scale': float(node.get('scale') or 1.0),
            'size': dict(node.get('size') or {}),
            'raw_kind': str(node.get('raw_kind') or ''),
            'text': str(node.get('text') or ''),
        }

        if semantic_role in {'player', 'goalkeeper', 'neutral', 'opponent', 'coach'}:
            entity.update(
                {
                    'team': _infer_player_team(node),
                    'role': _infer_player_role(node, semantic_role),
                    'number': _node_number(node),
                    'body_orientation': _infer_body_orientation(node),
                    'has_ball': False,
                }
            )
        elif semantic_role == 'ball':
            entity.update({'owner': None, 'trajectory': []})
        elif kind in {'cone', 'pole', 'goal'}:
            entity.update({'team': 'neutral'})
        elif kind == 'zone':
            entity.update({'zone_type': classify_zone_semantics(node)})
        elif kind == 'arrow':
            entity.update({'action_type': 'unknown_action'})

        if node_type == 'UnknownNode':
            warnings.append(f"Entidad {entity['id']} permanece como UnknownNode.")

        entities.append(entity)
    return entities


def _assign_ball_ownership(entities: List[Dict[str, Any]], warnings: List[str]) -> None:
    balls = [entity for entity in entities if str(entity.get('semantic_role') or '') == 'ball']
    player_like = [entity for entity in entities if str(entity.get('semantic_role') or '') in {'player', 'goalkeeper', 'neutral', 'opponent'}]
    for ball in balls:
        owner, distance = _nearest_entity(ball.get('position') or {}, player_like)
        if owner and distance <= 0.06:
            ball['owner'] = owner.get('id')
            owner['has_ball'] = True
        else:
            ball['owner'] = None
            if player_like:
                warnings.append(f"Balón {ball.get('id')} sin propietario claro.")


def _build_actions(objects: List[Dict[str, Any]], entities: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    ball_entities = [entity for entity in entities if str(entity.get('semantic_role') or '') == 'ball']
    ball_owner_id = str(ball_entities[0].get('owner') or '') if ball_entities else ''
    player_like = [entity for entity in entities if str(entity.get('semantic_role') or '') in {'player', 'goalkeeper', 'neutral', 'opponent'}]

    for node in objects:
        if not isinstance(node, dict):
            continue
        kind = str(node.get('kind') or '')
        if kind == 'arrow':
            points = node.get('points') if isinstance(node.get('points'), list) else []
            start_position = _safe_position(node)
            end_position = start_position
            if points:
                end_position = {
                    'x': float((points[-1] or {}).get('x') or start_position.get('x') or 0.0),
                    'y': float((points[-1] or {}).get('y') or start_position.get('y') or 0.0),
                    'z': 0.0,
                }
            nearest_start, _ = _nearest_entity(start_position, player_like)
            nearest_end, _ = _nearest_entity(end_position, player_like)
            action_type = classify_arrow_action(
                node,
                nearest_start_entity=nearest_start,
                nearest_end_entity=nearest_end,
                ball_owner_id=ball_owner_id or None,
            )
            actions.append(
                {
                    'id': f"action-{node.get('id')}",
                    'source_object_id': node.get('id'),
                    'type': action_type,
                    'from_entity': (nearest_start or {}).get('id'),
                    'to_entity': (nearest_end or {}).get('id'),
                    'points': list(points or []),
                    'style': dict(node.get('style') or {}),
                }
            )
            continue
        if kind == 'zone':
            zone_type = classify_zone_semantics(node)
            actions.append(
                {
                    'id': f"zone-{node.get('id')}",
                    'source_object_id': node.get('id'),
                    'type': zone_type,
                    'points': list(node.get('points') or []),
                    'text': str(node.get('text') or ''),
                }
            )

    if not actions:
        warnings.append('No se detectaron acciones ni zonas semánticas.')
    return actions


def _attach_ball_trajectories(base_entities: List[Dict[str, Any]], timeline_events: List[Dict[str, Any]], scene_graph: Dict[str, Any]) -> None:
    ball_entities = [entity for entity in base_entities if str(entity.get('semantic_role') or '') == 'ball']
    if not ball_entities:
        return
    raw_frames = scene_graph.get('timeline') if isinstance(scene_graph.get('timeline'), list) else []
    for ball in ball_entities:
        trajectory = [dict(ball.get('position') or {})]
        ball_id = str(ball.get('id') or '')
        for frame in raw_frames:
            objects = frame.get('objects') if isinstance(frame, dict) and isinstance(frame.get('objects'), list) else []
            for node in objects:
                if not isinstance(node, dict):
                    continue
                if str(node.get('id') or '') == ball_id or _semantic_kind(node) == 'ball':
                    trajectory.append(_safe_position(node))
                    break
        ball['trajectory'] = trajectory


def _frame_entities(frame: Dict[str, Any], warnings: List[str]) -> List[Dict[str, Any]]:
    objects = frame.get('objects') if isinstance(frame.get('objects'), list) else []
    frame_entities = _build_entities(objects, warnings)
    _assign_ball_ownership(frame_entities, warnings)
    return frame_entities


def _build_timeline_events(scene_graph: Dict[str, Any], base_entities: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    raw_frames = scene_graph.get('timeline') if isinstance(scene_graph.get('timeline'), list) else []
    if not raw_frames:
        return []

    timeline_events: List[Dict[str, Any]] = []
    prev_entities = base_entities
    prev_ball_owner = next((entity.get('owner') for entity in prev_entities if str(entity.get('semantic_role') or '') == 'ball'), None)

    for frame in raw_frames:
        if not isinstance(frame, dict):
            continue
        frame_warnings = list(frame.get('warnings') or [])
        curr_entities = _frame_entities(frame, frame_warnings)
        movement = summarize_timeline_movements(prev_entities, curr_entities)
        curr_ball_owner = next((entity.get('owner') for entity in curr_entities if str(entity.get('semantic_role') or '') == 'ball'), None)
        event = {
            'frame_index': int(frame.get('index') or len(timeline_events)),
            'title': str(frame.get('title') or f'Frame {len(timeline_events) + 1}').strip(),
            'duration': int(frame.get('duration') or 0),
            'moved_entities': movement.get('moved_entities') or [],
            'ball_owner_before': prev_ball_owner,
            'ball_owner_after': curr_ball_owner,
            'possession_changed': prev_ball_owner != curr_ball_owner,
            'warnings': frame_warnings,
        }
        timeline_events.append(event)
        for warning in frame_warnings:
            warnings.append(f"Timeline {event['title']}: {warning}")
        prev_entities = curr_entities
        prev_ball_owner = curr_ball_owner
    return timeline_events


def build_semantic_graph_from_scene_graph(scene_graph: Dict[str, Any]) -> Dict[str, Any]:
    warnings = list(scene_graph.get('warnings') or [])
    field = dict(scene_graph.get('field') or {})
    metadata = dict(scene_graph.get('metadata') or {})
    objects = [node for node in (scene_graph.get('objects') or []) if isinstance(node, dict)]

    entities = _build_entities(objects, warnings)
    _assign_ball_ownership(entities, warnings)
    actions = _build_actions(objects, entities, warnings)
    timeline_events = _build_timeline_events(scene_graph, entities, warnings)
    _attach_ball_trajectories(entities, timeline_events, scene_graph)

    return {
        'field': field,
        'entities': entities,
        'actions': actions,
        'timeline_events': timeline_events,
        'metadata': metadata,
        'warnings': warnings,
    }


def _semantic_summary(semantic_graph: Dict[str, Any]) -> Dict[str, Any]:
    entities = [entity for entity in (semantic_graph.get('entities') or []) if isinstance(entity, dict)]
    actions = [action for action in (semantic_graph.get('actions') or []) if isinstance(action, dict)]
    timeline_events = [event for event in (semantic_graph.get('timeline_events') or []) if isinstance(event, dict)]
    players = [entity for entity in entities if str(entity.get('semantic_role') or '') in {'player', 'goalkeeper', 'neutral', 'opponent'}]
    balls = [entity for entity in entities if str(entity.get('semantic_role') or '') == 'ball']
    arrows = [action for action in actions if str(action.get('type') or '').endswith('action') or str(action.get('type') or '') in {'run', 'pass', 'dribble', 'pressure', 'cover', 'support'}]
    return {
        'entity_count': len(entities),
        'player_count': len(players),
        'ball_count': len(balls),
        'action_count': len(actions),
        'arrow_action_count': len(arrows),
        'timeline_event_count': len(timeline_events),
        'players': players[:24],
        'balls': balls[:8],
        'actions': actions[:24],
        'timeline_events': timeline_events[:24],
        'warnings': list(semantic_graph.get('warnings') or []),
    }


def build_semantic_graph_debug_html(task: Any) -> str:
    from .service import build_scene_graph_from_task

    semantic_graph = build_semantic_graph_from_scene_graph(build_scene_graph_from_task(task))
    summary = _semantic_summary(semantic_graph)
    payload_json = json.dumps(summary, ensure_ascii=False, indent=2)
    task_id = getattr(task, 'id', None)
    task_title = str((semantic_graph.get('metadata') or {}).get('task_title') or getattr(task, 'title', '') or '').strip() or f'Tarea {task_id}'
    warnings_html = ''.join(f'<li>{warning}</li>' for warning in summary['warnings']) or '<li>Sin warnings.</li>'
    entities_html = ''.join(
        f"<tr><td>{entity.get('id')}</td><td>{entity.get('semantic_role')}</td><td>{entity.get('team', '-')}</td><td>{entity.get('number', '-')}</td><td>{entity.get('has_ball', False)}</td></tr>"
        for entity in summary['players']
    ) or '<tr><td colspan="5">Sin jugadores detectados.</td></tr>'
    balls_html = ''.join(
        f"<tr><td>{ball.get('id')}</td><td>{ball.get('owner') or '-'}</td><td>{ball.get('position', {}).get('x', 0):.4f}</td><td>{ball.get('position', {}).get('y', 0):.4f}</td></tr>"
        for ball in summary['balls']
    ) or '<tr><td colspan="4">Sin balón detectado.</td></tr>'
    actions_html = ''.join(
        f"<tr><td>{action.get('id')}</td><td>{action.get('type')}</td><td>{action.get('from_entity') or '-'}</td><td>{action.get('to_entity') or '-'}</td></tr>"
        for action in summary['actions']
    ) or '<tr><td colspan="4">Sin acciones detectadas.</td></tr>'
    timeline_html = ''.join(
        f"<tr><td>{event.get('frame_index')}</td><td>{event.get('title')}</td><td>{len(event.get('moved_entities') or [])}</td><td>{'Sí' if event.get('possession_changed') else 'No'}</td></tr>"
        for event in summary['timeline_events']
    ) or '<tr><td colspan="4">Sin eventos de timeline.</td></tr>'

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Semantic Graph Debug · {task_title}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #07111f;
      color: #e5e7eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr .8fr;
      gap: 18px;
    }}
    .card {{
      background: #111827;
      border: 1px solid rgba(148,163,184,.18);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0,0,0,.22);
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 18px;
      font-size: 18px;
      background: #0f172a;
      border-bottom: 1px solid rgba(148,163,184,.16);
    }}
    .body {{ padding: 16px 18px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: #0f172a;
      border: 1px solid rgba(148,163,184,.12);
      border-radius: 12px;
      padding: 12px;
    }}
    .stat small {{
      display: block;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 6px;
    }}
    .stat strong {{
      font-size: 20px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid rgba(148,163,184,.12);
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #93c5fd; font-weight: 700; }}
    ul {{ margin: 0; padding-left: 18px; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.5;
      color: #cbd5e1;
    }}
    @media (max-width: 1100px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="grid">
    <section class="card">
      <h2>Resumen semántico</h2>
      <div class="body">
        <div class="stats">
          <div class="stat"><small>Task ID</small><strong>{task_id or '-'}</strong></div>
          <div class="stat"><small>Jugadores</small><strong>{summary['player_count']}</strong></div>
          <div class="stat"><small>Balones</small><strong>{summary['ball_count']}</strong></div>
          <div class="stat"><small>Actions</small><strong>{summary['action_count']}</strong></div>
        </div>
        <h3>Warnings</h3>
        <ul>{warnings_html}</ul>
        <h3>Jugadores detectados</h3>
        <table>
          <thead><tr><th>ID</th><th>Semantic role</th><th>Team</th><th>Número</th><th>Has ball</th></tr></thead>
          <tbody>{entities_html}</tbody>
        </table>
        <h3 style="margin-top:20px;">Balón</h3>
        <table>
          <thead><tr><th>ID</th><th>Owner</th><th>X</th><th>Y</th></tr></thead>
          <tbody>{balls_html}</tbody>
        </table>
        <h3 style="margin-top:20px;">Acciones detectadas</h3>
        <table>
          <thead><tr><th>ID</th><th>Tipo</th><th>Desde</th><th>Hacia</th></tr></thead>
          <tbody>{actions_html}</tbody>
        </table>
      </div>
    </section>
    <section class="card">
      <h2>Timeline y JSON</h2>
      <div class="body">
        <h3>Timeline events</h3>
        <table>
          <thead><tr><th>Frame</th><th>Título</th><th>Movimientos</th><th>Cambio de posesión</th></tr></thead>
          <tbody>{timeline_html}</tbody>
        </table>
        <h3 style="margin-top:20px;">JSON resumido</h3>
        <pre>{payload_json}</pre>
      </div>
    </section>
  </div>
</body>
</html>"""


def write_semantic_graph_debug_html(task: Any, out_path: str | Path | None = None) -> Path:
    target = Path(out_path).expanduser() if out_path else (Path.home() / 'Downloads' / 'semantic_graph_debug.html')
    html = build_semantic_graph_debug_html(task)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding='utf-8')
    return target


__all__ = [
    'build_semantic_graph_from_scene_graph',
    'build_semantic_graph_debug_html',
    'write_semantic_graph_debug_html',
]
