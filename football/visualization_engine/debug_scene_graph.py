from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .service import build_scene_graph_from_task


SVG_WIDTH = 1000
SVG_HEIGHT = 650


def _object_is_outside(node: Dict[str, Any]) -> bool:
    position = node.get('position') if isinstance(node.get('position'), dict) else {}
    x = float(position.get('x') or 0.0)
    y = float(position.get('y') or 0.0)
    return x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0


def _collect_exact_overlaps(objects: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index: Dict[Tuple[float, float], List[str]] = {}
    for node in objects:
        if not isinstance(node, dict):
            continue
        position = node.get('position') if isinstance(node.get('position'), dict) else {}
        x = round(float(position.get('x') or 0.0), 6)
        y = round(float(position.get('y') or 0.0), 6)
        index.setdefault((x, y), []).append(str(node.get('id') or 'node'))
    overlaps: List[Dict[str, Any]] = []
    for (x, y), node_ids in index.items():
        if len(node_ids) < 2:
            continue
        overlaps.append({'x': x, 'y': y, 'node_ids': node_ids})
    return overlaps


def _prepare_frame(index: int, title: str, objects: List[Dict[str, Any]], *, warnings: List[str] | None = None) -> Dict[str, Any]:
    safe_objects = [node for node in (objects or []) if isinstance(node, dict)]
    unknown_nodes = [str(node.get('id') or 'node') for node in safe_objects if str(node.get('type') or '') == 'UnknownNode']
    outside_nodes = [str(node.get('id') or 'node') for node in safe_objects if _object_is_outside(node)]
    overlaps = _collect_exact_overlaps(safe_objects)
    return {
        'index': index,
        'title': title,
        'objects': safe_objects,
        'warnings': list(warnings or []),
        'unknown_nodes': unknown_nodes,
        'outside_nodes': outside_nodes,
        'overlaps': overlaps,
    }


def _build_debug_payload(task: Any) -> Dict[str, Any]:
    scene_graph = build_scene_graph_from_task(task)
    metadata = dict(scene_graph.get('metadata') or {})
    base_objects = [node for node in (scene_graph.get('objects') or []) if isinstance(node, dict)]
    frames = [
        _prepare_frame(
            0,
            'Vista base',
            base_objects,
            warnings=scene_graph.get('warnings') or [],
        )
    ]

    raw_timeline = scene_graph.get('timeline') if isinstance(scene_graph.get('timeline'), list) else []
    for raw_frame in raw_timeline:
        if not isinstance(raw_frame, dict):
            continue
        frame_index = int(raw_frame.get('index') or len(frames))
        frame_title = str(raw_frame.get('title') or f'Frame {frame_index + 1}').strip() or f'Frame {frame_index + 1}'
        frames.append(
            _prepare_frame(
                frame_index + 1,
                frame_title,
                raw_frame.get('objects') if isinstance(raw_frame.get('objects'), list) else [],
                warnings=raw_frame.get('warnings') or [],
            )
        )

    payload = {
        'task': {
            'id': getattr(task, 'id', None),
            'title': metadata.get('task_title') or str(getattr(task, 'title', '') or '').strip() or f'Tarea {getattr(task, "id", "")}',
            'session_id': metadata.get('session_id'),
        },
        'field': scene_graph.get('field') or {},
        'metadata': metadata,
        'warnings': list(scene_graph.get('warnings') or []),
        'objects': base_objects,
        'frames': frames,
        'summary': {
            'object_count': len(base_objects),
            'frame_count': max(0, len(frames) - 1),
            'unknown_nodes': [str(node.get('id') or 'node') for node in base_objects if str(node.get('type') or '') == 'UnknownNode'],
            'outside_nodes': [str(node.get('id') or 'node') for node in base_objects if _object_is_outside(node)],
            'overlaps': _collect_exact_overlaps(base_objects),
        },
    }
    return payload


def build_scene_graph_debug_html(task: Any) -> str:
    payload = _build_debug_payload(task)
    payload_json = json.dumps(payload, ensure_ascii=False)
    title = str(payload.get('task', {}).get('title') or 'Scene Graph Debug')
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scene Graph Debug · {title}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --line: #334155;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #22c55e;
      --danger: #ef4444;
      --warning: #f59e0b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #020617;
      color: var(--text);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 16px;
      min-height: 100vh;
      padding: 16px;
    }}
    .main {{
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(31,41,55,.96), rgba(15,23,42,.96));
      border: 1px solid rgba(148,163,184,.18);
      border-radius: 16px;
      box-shadow: 0 12px 40px rgba(0,0,0,.22);
      overflow: hidden;
    }}
    .panel-header {{
      padding: 14px 18px;
      border-bottom: 1px solid rgba(148,163,184,.14);
      font-weight: 700;
      letter-spacing: .02em;
      background: rgba(255,255,255,.02);
    }}
    .panel-body {{ padding: 16px 18px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}
    .stat {{
      padding: 12px 14px;
      border-radius: 12px;
      background: rgba(15,23,42,.7);
      border: 1px solid rgba(148,163,184,.12);
    }}
    .stat-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 6px;
    }}
    .stat-value {{
      font-size: 20px;
      font-weight: 800;
      line-height: 1.1;
    }}
    .warnings-list, .timeline-buttons, .side-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .warning-chip, .meta-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(239,68,68,.12);
      border: 1px solid rgba(239,68,68,.22);
      color: #fecaca;
    }}
    .warning-chip.warning {{
      background: rgba(245,158,11,.12);
      border-color: rgba(245,158,11,.22);
      color: #fde68a;
    }}
    .canvas-wrap {{
      padding: 14px;
      background: radial-gradient(circle at top, rgba(34,197,94,.08), rgba(2,6,23,0));
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
      background: #0b1220;
      border-radius: 16px;
      border: 1px solid rgba(148,163,184,.16);
    }}
    .timeline-buttons button {{
      appearance: none;
      border: 1px solid rgba(148,163,184,.18);
      background: rgba(15,23,42,.85);
      color: var(--text);
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      font-weight: 700;
    }}
    .timeline-buttons button.active {{
      background: rgba(34,197,94,.18);
      border-color: rgba(34,197,94,.4);
      color: #dcfce7;
    }}
    .side-panel {{
      position: sticky;
      top: 16px;
      height: fit-content;
      display: grid;
      gap: 16px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
      font-size: 14px;
    }}
    .detail-grid strong {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 4px;
    }}
    .hint {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .legend {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      color: var(--muted);
    }}
    .legend-swatch {{
      width: 14px;
      height: 14px;
      border-radius: 4px;
      border: 1px solid rgba(255,255,255,.2);
      flex: 0 0 auto;
    }}
    @media (max-width: 1100px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .side-panel {{ position: static; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <div class="main">
      <section class="panel">
        <div class="panel-header">Scene Graph Debug</div>
        <div class="panel-body">
          <div class="stats">
            <div class="stat"><span class="stat-label">Task ID</span><span class="stat-value">{payload['task']['id'] or '-'}</span></div>
            <div class="stat"><span class="stat-label">Título</span><span class="stat-value">{title}</span></div>
            <div class="stat"><span class="stat-label">Objetos</span><span class="stat-value">{payload['summary']['object_count']}</span></div>
            <div class="stat"><span class="stat-label">Frames</span><span class="stat-value">{payload['summary']['frame_count']}</span></div>
            <div class="stat"><span class="stat-label">Warnings</span><span class="stat-value">{len(payload['warnings'])}</span></div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">Canvas SVG</div>
        <div class="canvas-wrap">
          <svg id="scene-svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" preserveAspectRatio="xMidYMid meet" aria-label="Scene graph debug canvas">
            <defs>
              <marker id="arrow-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f43f5e"></path>
              </marker>
            </defs>
          </svg>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">Timeline</div>
        <div class="panel-body">
          <div id="timeline-buttons" class="timeline-buttons"></div>
        </div>
      </section>
    </div>
    <aside class="side-panel">
      <section class="panel">
        <div class="panel-header">Validaciones automáticas</div>
        <div class="panel-body">
          <div id="validation-summary" class="warnings-list"></div>
          <div id="validation-details" class="mono" style="margin-top:12px;"></div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">Leyenda</div>
        <div class="panel-body">
          <div class="legend">
            <div class="legend-item"><span class="legend-swatch" style="background:#2563eb"></span>Jugador</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#f97316"></span>Portero</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#ffffff"></span>Balón</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#facc15"></span>Cono</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#ef4444"></span>Pica</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#94a3b8"></span>Portería</div>
            <div class="legend-item"><span class="legend-swatch" style="background:#f43f5e"></span>Flecha</div>
            <div class="legend-item"><span class="legend-swatch" style="background:rgba(34,197,94,.35)"></span>Zona</div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">Objeto seleccionado</div>
        <div class="panel-body">
          <div id="selected-hint" class="hint">Haz clic en cualquier objeto del SVG para inspeccionarlo.</div>
          <div id="object-details" class="detail-grid" hidden></div>
        </div>
      </section>
    </aside>
  </div>
  <script>
    const DEBUG_DATA = {payload_json};
    const SVG_W = {SVG_WIDTH};
    const SVG_H = {SVG_HEIGHT};
    const svg = document.getElementById('scene-svg');
    const timelineButtons = document.getElementById('timeline-buttons');
    const selectedHint = document.getElementById('selected-hint');
    const objectDetails = document.getElementById('object-details');
    const validationSummary = document.getElementById('validation-summary');
    const validationDetails = document.getElementById('validation-details');
    let activeFrame = DEBUG_DATA.frames[0];
    let activeNodeId = null;

    function fieldX(value) {{
      return Math.max(-0.15, Math.min(1.15, Number(value || 0))) * SVG_W;
    }}

    function fieldY(value) {{
      return Math.max(-0.15, Math.min(1.15, Number(value || 0))) * SVG_H;
    }}

    function objectLabel(node) {{
      const text = String(node.text || '').trim();
      if (text) return text;
      const id = String(node.id || '');
      const parts = id.split('-');
      return parts[parts.length - 1] || '?';
    }}

    function clearSvg() {{
      svg.querySelectorAll('.dynamic-node').forEach((node) => node.remove());
    }}

    function appendSvg(node) {{
      node.classList.add('dynamic-node');
      svg.appendChild(node);
    }}

    function create(tag, attrs = {{}}, text = '') {{
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attrs).forEach(([key, value]) => {{
        if (value !== null && value !== undefined) {{
          node.setAttribute(key, String(value));
        }}
      }});
      if (text) node.textContent = text;
      return node;
    }}

    function drawField() {{
      appendSvg(create('rect', {{ x: 0, y: 0, width: SVG_W, height: SVG_H, rx: 24, fill: '#2e7d32' }}));
      appendSvg(create('rect', {{ x: 12, y: 12, width: SVG_W - 24, height: SVG_H - 24, rx: 20, fill: '#348a3a', stroke: '#e5e7eb', 'stroke-width': 3 }}));
      for (let i = 0; i < 10; i += 1) {{
        const x = 20 + (i * ((SVG_W - 40) / 10));
        appendSvg(create('rect', {{
          x,
          y: 14,
          width: (SVG_W - 40) / 10,
          height: SVG_H - 28,
          fill: i % 2 === 0 ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
        }}));
      }}
      appendSvg(create('line', {{ x1: SVG_W / 2, y1: 14, x2: SVG_W / 2, y2: SVG_H - 14, stroke: '#ffffff', 'stroke-width': 3 }}));
      appendSvg(create('circle', {{ cx: SVG_W / 2, cy: SVG_H / 2, r: 74, fill: 'none', stroke: '#ffffff', 'stroke-width': 3 }}));
      appendSvg(create('circle', {{ cx: SVG_W / 2, cy: SVG_H / 2, r: 4, fill: '#ffffff' }}));
    }}

    function registerSelectable(node, objectData) {{
      node.style.cursor = 'pointer';
      node.addEventListener('click', (event) => {{
        event.stopPropagation();
        activeNodeId = objectData.id;
        renderDetails(objectData);
        renderFrame(activeFrame.index);
      }});
    }}

    function drawZone(node, danger) {{
      const points = Array.isArray(node.points) ? node.points : [];
      if (points.length >= 3) {{
        const pointsAttr = points.map((point) => `${{fieldX(point.x)}},${{fieldY(point.y)}}`).join(' ');
        const shape = create('polygon', {{
          points: pointsAttr,
          fill: danger ? 'rgba(239,68,68,0.28)' : 'rgba(34,197,94,0.24)',
          stroke: danger ? '#ef4444' : '#22c55e',
          'stroke-width': 2,
          'stroke-dasharray': '8 6',
        }});
        registerSelectable(shape, node);
        appendSvg(shape);
        return;
      }}
      const width = Math.max(24, Number((((node.size || {{}}).width) || 0) * SVG_W));
      const height = Math.max(24, Number((((node.size || {{}}).height) || 0) * SVG_H));
      const shape = create('rect', {{
        x: fieldX(node.position.x) - (width / 2),
        y: fieldY(node.position.y) - (height / 2),
        width,
        height,
        fill: danger ? 'rgba(239,68,68,0.22)' : 'rgba(34,197,94,0.20)',
        stroke: danger ? '#ef4444' : '#22c55e',
        'stroke-width': 2,
        'stroke-dasharray': '8 6',
        rx: 10,
      }});
      registerSelectable(shape, node);
      appendSvg(shape);
    }}

    function drawArrow(node, danger) {{
      const px = fieldX(node.position.x);
      const py = fieldY(node.position.y);
      const points = Array.isArray(node.points) ? node.points : [];
      const segments = [`M ${{px}} ${{py}}`];
      if (points.length) {{
        points.forEach((point) => segments.push(`L ${{fieldX(point.x)}} ${{fieldY(point.y)}}`));
      }} else {{
        const width = Math.max(40, Number((((node.size || {{}}).width) || 0) * SVG_W));
        const height = Number((((node.size || {{}}).height) || 0) * SVG_H);
        segments.push(`L ${{px + width}} ${{py + height}}`);
      }}
      const path = create('path', {{
        d: segments.join(' '),
        fill: 'none',
        stroke: danger ? '#ef4444' : '#f43f5e',
        'stroke-width': 4,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'marker-end': 'url(#arrow-head)',
      }});
      registerSelectable(path, node);
      appendSvg(path);
    }}

    function drawLabel(node, x, y, label, fill = '#ffffff', fontSize = 16) {{
      const text = create('text', {{
        x,
        y,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill,
        'font-size': fontSize,
        'font-weight': 800,
      }}, label);
      appendSvg(text);
    }}

    function drawObject(node) {{
      const kind = String(node.kind || 'unknown');
      const danger = Boolean(node.__outside);
      const x = fieldX(node.position.x);
      const y = fieldY(node.position.y);
      const label = objectLabel(node);
      if (kind === 'zone') {{
        drawZone(node, danger);
        return;
      }}
      if (kind === 'arrow') {{
        drawArrow(node, danger);
        return;
      }}
      if (kind === 'text') {{
        const rect = create('rect', {{
          x: x - 68,
          y: y - 18,
          width: 136,
          height: 36,
          rx: 10,
          fill: danger ? 'rgba(239,68,68,.92)' : 'rgba(15,23,42,.88)',
          stroke: danger ? '#ef4444' : '#cbd5e1',
          'stroke-width': 2,
        }});
        registerSelectable(rect, node);
        appendSvg(rect);
        drawLabel(node, x, y, label || 'Texto', '#ffffff', 14);
        return;
      }}
      if (kind === 'goal') {{
        const width = Math.max(54, Number((((node.size || {{}}).width) || 0) * SVG_W) || 84);
        const height = Math.max(18, Number((((node.size || {{}}).height) || 0) * SVG_H) || 28);
        const goal = create('rect', {{
          x: x - (width / 2),
          y: y - (height / 2),
          width,
          height,
          rx: 4,
          fill: danger ? '#ef4444' : '#9ca3af',
          stroke: '#e5e7eb',
          'stroke-width': 2,
        }});
        registerSelectable(goal, node);
        appendSvg(goal);
        return;
      }}
      if (kind === 'pole') {{
        const pole = create('rect', {{
          x: x - 6,
          y: y - 24,
          width: 12,
          height: 48,
          rx: 3,
          fill: danger ? '#ef4444' : '#dc2626',
          stroke: '#fee2e2',
          'stroke-width': 2,
        }});
        registerSelectable(pole, node);
        appendSvg(pole);
        return;
      }}
      if (kind === 'cone') {{
        const points = `${{x}},${{y - 18}} ${{x - 16}},${{y + 16}} ${{x + 16}},${{y + 16}}`;
        const cone = create('polygon', {{
          points,
          fill: danger ? '#ef4444' : '#facc15',
          stroke: danger ? '#fecaca' : '#854d0e',
          'stroke-width': 2,
        }});
        registerSelectable(cone, node);
        appendSvg(cone);
        return;
      }}

      const fillMap = {{
        player: '#2563eb',
        goalkeeper: '#f97316',
        ball: '#ffffff',
        unknown: '#ef4444',
      }};
      const strokeMap = {{
        player: '#dbeafe',
        goalkeeper: '#ffedd5',
        ball: '#111827',
        unknown: '#fee2e2',
      }};
      const radiusMap = {{
        player: 16,
        goalkeeper: 17,
        ball: 10,
        unknown: 14,
      }};
      const circle = create('circle', {{
        cx: x,
        cy: y,
        r: radiusMap[kind] || 15,
        fill: danger ? '#ef4444' : (fillMap[kind] || '#64748b'),
        stroke: strokeMap[kind] || '#e5e7eb',
        'stroke-width': kind === 'ball' ? 3 : 2.5,
      }});
      registerSelectable(circle, node);
      appendSvg(circle);
      if (kind !== 'ball') {{
        drawLabel(node, x, y, label, '#ffffff', 14);
      }}
    }}

    function renderDetails(node) {{
      selectedHint.hidden = true;
      objectDetails.hidden = false;
      const size = node.size || {{}};
      const position = node.position || {{}};
      const rows = [
        ['id', node.id],
        ['kind', node.kind],
        ['semantic_role', node.semantic_role || '-'],
        ['x', Number(position.x || 0).toFixed(4)],
        ['y', Number(position.y || 0).toFixed(4)],
        ['rotation', Number(node.rotation || 0).toFixed(2)],
        ['scale', Number(node.scale || 1).toFixed(2)],
        ['width', Number(size.width || 0).toFixed(4)],
        ['height', Number(size.height || 0).toFixed(4)],
        ['raw_kind', node.raw_kind || '-'],
      ];
      objectDetails.innerHTML = rows.map(([label, value]) => `
        <div><strong>${{label}}</strong><span>${{value}}</span></div>
      `).join('');
    }}

    function renderValidations(frame) {{
      const chips = [];
      if (frame.warnings && frame.warnings.length) {{
        chips.push(...frame.warnings.map((warning) => `<span class="warning-chip warning">${{warning}}</span>`));
      }}
      if (frame.outside_nodes && frame.outside_nodes.length) {{
        chips.push(`<span class="warning-chip">${{frame.outside_nodes.length}} objeto(s) fuera del campo</span>`);
      }}
      if (frame.unknown_nodes && frame.unknown_nodes.length) {{
        chips.push(`<span class="warning-chip">${{frame.unknown_nodes.length}} UnknownNode</span>`);
      }}
      if (frame.overlaps && frame.overlaps.length) {{
        chips.push(`<span class="warning-chip warning">${{frame.overlaps.length}} solapamiento(s) exacto(s)</span>`);
      }}
      if (!chips.length) {{
        chips.push('<span class="meta-chip">Sin incidencias automáticas</span>');
      }}
      validationSummary.innerHTML = chips.join('');

      const lines = [];
      if (frame.outside_nodes && frame.outside_nodes.length) {{
        lines.push(`Fuera del campo: ${{frame.outside_nodes.join(', ')}}`);
      }}
      if (frame.unknown_nodes && frame.unknown_nodes.length) {{
        lines.push(`UnknownNode: ${{frame.unknown_nodes.join(', ')}}`);
      }}
      if (frame.overlaps && frame.overlaps.length) {{
        frame.overlaps.forEach((overlap) => {{
          lines.push(`Solapamiento exacto en (${{overlap.x}}, ${{overlap.y}}): ${{overlap.node_ids.join(', ')}}`);
        }});
      }}
      validationDetails.textContent = lines.join('\\n') || 'Sin detalles adicionales.';
    }}

    function renderTimelineButtons() {{
      timelineButtons.innerHTML = '';
      DEBUG_DATA.frames.forEach((frame) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = frame.index === 0 ? 'Vista base' : `Ver Frame · ${{frame.title}}`;
        if (activeFrame.index === frame.index) {{
          button.classList.add('active');
        }}
        button.addEventListener('click', () => renderFrame(frame.index));
        timelineButtons.appendChild(button);
      }});
    }}

    function renderFrame(frameIndex) {{
      activeFrame = DEBUG_DATA.frames.find((frame) => frame.index === frameIndex) || DEBUG_DATA.frames[0];
      clearSvg();
      drawField();
      const objects = (activeFrame.objects || []).map((node) => ({{
        ...node,
        __outside: (activeFrame.outside_nodes || []).includes(String(node.id || '')),
      }}));
      objects.forEach(drawObject);
      renderTimelineButtons();
      renderValidations(activeFrame);
      if (activeNodeId) {{
        const selected = objects.find((node) => String(node.id || '') === activeNodeId);
        if (selected) {{
          renderDetails(selected);
        }}
      }}
    }}

    svg.addEventListener('click', () => {{
      activeNodeId = null;
      objectDetails.hidden = true;
      selectedHint.hidden = false;
    }});

    renderFrame(0);
  </script>
</body>
</html>"""


def write_scene_graph_debug_html(task: Any, out_path: str | Path | None = None) -> Path:
    target = Path(out_path).expanduser() if out_path else (Path.home() / 'Downloads' / 'scene_graph_debug.html')
    html = build_scene_graph_debug_html(task)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding='utf-8')
    return target


__all__ = [
    'build_scene_graph_debug_html',
    'write_scene_graph_debug_html',
]
