from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.core.management.base import BaseCommand, CommandError

from football.models import SessionTask
from football.visualization_engine import build_visualization_blueprint, summarize_visualization_blueprint


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _list_html(items: Iterable[str]) -> str:
    safe_items = [str(item) for item in items if str(item).strip()]
    if not safe_items:
        return '<li>Sin datos.</li>'
    return ''.join(f'<li>{item}</li>' for item in safe_items)


def _table_html(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return '<tr><td colspan="{0}">Sin datos.</td></tr>'.format(len(columns))
    html_rows: List[str] = []
    for row in rows:
        cells = ''.join(f'<td>{row.get(column, "")}</td>' for column in columns)
        html_rows.append(f'<tr>{cells}</tr>')
    return ''.join(html_rows)


def _sprite_summary_rows(sprites: Iterable[Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sprite in sprites:
        bounds = sprite.bounds() if hasattr(sprite, 'bounds') else {}
        anchor = sprite.anchor() if hasattr(sprite, 'anchor') else {}
        rows.append(
            {
                'id': getattr(sprite, 'sprite_id', ''),
                'type': sprite.__class__.__name__,
                'semantic_role': getattr(sprite, 'semantic_role', ''),
                'z_index': getattr(sprite, 'z_index', ''),
                'rotation': getattr(sprite, 'rotation', ''),
                'scale': getattr(sprite, 'scale', ''),
                'anchor': _json_dump(anchor),
                'bounds': _json_dump(bounds),
            }
        )
    return rows


def build_visualization_blueprint_debug_html(task: SessionTask) -> str:
    blueprint = build_visualization_blueprint(task)
    summary = summarize_visualization_blueprint(blueprint)
    scene_graph = blueprint.get('scene_graph') or {}
    semantic_graph = blueprint.get('semantic_graph') or {}
    sprites = list(blueprint.get('sprites') or [])
    theme = blueprint.get('theme') or {}
    asset_registry = blueprint.get('asset_registry')
    top2d_renderer = blueprint.get('renderer_top2d')
    perspective_renderer = blueprint.get('renderer_perspective3d')

    top2d_output = top2d_renderer.render(sprites, metadata={'task_id': task.id}) if top2d_renderer else {}
    perspective_output = perspective_renderer.render(sprites, metadata={'task_id': task.id}) if perspective_renderer else {}

    asset_payload = []
    if asset_registry is not None and hasattr(asset_registry, 'all_manifests'):
        asset_payload = [manifest.as_dict() for manifest in asset_registry.all_manifests()]

    warnings = list(scene_graph.get('warnings') or []) + list(semantic_graph.get('warnings') or [])
    sprite_rows = _sprite_summary_rows(sprites)
    scene_rows = [
        {'label': 'Task ID', 'value': task.id},
        {'label': 'Título', 'value': task.title or '-'},
        {'label': 'Objetos Scene Graph', 'value': len(scene_graph.get('objects') or [])},
        {'label': 'Frames Scene Graph', 'value': len(scene_graph.get('timeline') or [])},
        {'label': 'Warnings Scene Graph', 'value': len(scene_graph.get('warnings') or [])},
    ]
    semantic_rows = [
        {'label': 'Entidades', 'value': len(semantic_graph.get('entities') or [])},
        {'label': 'Acciones', 'value': len(semantic_graph.get('actions') or [])},
        {'label': 'Timeline events', 'value': len(semantic_graph.get('timeline_events') or [])},
        {'label': 'Warnings Semantic Graph', 'value': len(semantic_graph.get('warnings') or [])},
        {'label': 'Sprites generados', 'value': summary.get('sprite_count', 0)},
    ]

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualization Blueprint Debug · Task {task.id}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #08111d;
      color: #e5e7eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .card {{
      background: #111827;
      border: 1px solid rgba(148, 163, 184, .14);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 18px 42px rgba(0, 0, 0, .24);
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 18px;
      font-size: 17px;
      background: #0f172a;
      border-bottom: 1px solid rgba(148, 163, 184, .14);
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
      border: 1px solid rgba(148, 163, 184, .12);
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
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid rgba(148, 163, 184, .12);
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #93c5fd; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
      color: #cbd5e1;
    }}
    ul {{ margin: 0; padding-left: 18px; }}
    .wide {{ grid-column: 1 / -1; }}
    @media (max-width: 1100px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="stats">
    <div class="stat"><small>Task ID</small><strong>{task.id}</strong></div>
    <div class="stat"><small>Tema</small><strong>{theme.get('key', '-')}</strong></div>
    <div class="stat"><small>Sprites</small><strong>{summary.get('sprite_count', 0)}</strong></div>
    <div class="stat"><small>Actions</small><strong>{summary.get('action_count', 0)}</strong></div>
  </div>

  <div class="grid">
    <section class="card">
      <h2>1. Resumen Scene Graph</h2>
      <div class="body">
        <table>
          <thead><tr><th>Campo</th><th>Valor</th></tr></thead>
          <tbody>{_table_html(scene_rows, ['label', 'value'])}</tbody>
        </table>
        <h3>Warnings</h3>
        <ul>{_list_html(scene_graph.get('warnings') or [])}</ul>
      </div>
    </section>

    <section class="card">
      <h2>2. Resumen Semantic Graph</h2>
      <div class="body">
        <table>
          <thead><tr><th>Campo</th><th>Valor</th></tr></thead>
          <tbody>{_table_html(semantic_rows, ['label', 'value'])}</tbody>
        </table>
        <h3>Warnings</h3>
        <ul>{_list_html(semantic_graph.get('warnings') or [])}</ul>
      </div>
    </section>

    <section class="card wide">
      <h2>3. Lista de sprites generados</h2>
      <div class="body">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Type</th><th>Semantic role</th><th>Z</th><th>Rot</th><th>Scale</th><th>Anchor</th><th>Bounds</th>
            </tr>
          </thead>
          <tbody>{_table_html(sprite_rows, ['id', 'type', 'semantic_role', 'z_index', 'rotation', 'scale', 'anchor', 'bounds'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>4. Draw calls Top2DRenderer</h2>
      <div class="body"><pre>{_json_dump(top2d_output)}</pre></div>
    </section>

    <section class="card">
      <h2>5. Draw calls Perspective3DRenderer</h2>
      <div class="body"><pre>{_json_dump(perspective_output)}</pre></div>
    </section>

    <section class="card">
      <h2>6. Theme usado</h2>
      <div class="body"><pre>{_json_dump(theme)}</pre></div>
    </section>

    <section class="card">
      <h2>7. Asset registry usado</h2>
      <div class="body"><pre>{_json_dump(asset_payload)}</pre></div>
    </section>

    <section class="card wide">
      <h2>8. Warnings consolidados</h2>
      <div class="body"><ul>{_list_html(warnings)}</ul></div>
    </section>
  </div>
</body>
</html>"""


class Command(BaseCommand):
    help = 'Genera un HTML autónomo con el diagnóstico completo del Visualization Blueprint.'

    def add_arguments(self, parser):
        parser.add_argument('--task', type=int, default=0, help='ID de SessionTask.')
        parser.add_argument('--out', type=str, default='', help='Ruta opcional de salida para el HTML.')

    def handle(self, *args, **options):
        task_id = int(options.get('task') or 0)
        out_raw = str(options.get('out') or '').strip()

        task = None
        if task_id > 0:
            task = SessionTask.objects.select_related('session').filter(id=task_id).first()
            if not task:
                raise CommandError(f'No existe SessionTask #{task_id}.')
        else:
            task = SessionTask.objects.select_related('session').order_by('-id').first()
            if not task:
                raise CommandError('No hay SessionTask disponibles para generar el diagnóstico.')

        out_path = Path(out_raw).expanduser() if out_raw else (Path.home() / 'Downloads' / 'visualization_blueprint_debug.html')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_visualization_blueprint_debug_html(task), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(str(out_path)))
