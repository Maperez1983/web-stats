from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.core.management.base import BaseCommand, CommandError

from football.models import SessionTask
from football.visualization_engine import build_visualization_blueprint, build_visualization_scene


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _list_html(items: Iterable[str]) -> str:
    values = [str(item) for item in items if str(item).strip()]
    if not values:
        return '<li>Sin datos.</li>'
    return ''.join(f'<li>{value}</li>' for value in values)


def _table_html(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return '<tr><td colspan="{0}">Sin datos.</td></tr>'.format(len(columns))
    html_rows: List[str] = []
    for row in rows:
        cells = ''.join(f'<td>{row.get(column, "")}</td>' for column in columns)
        html_rows.append(f'<tr>{cells}</tr>')
    return ''.join(html_rows)


def _sprite_row(sprite: Any, layer_name: str, layer_z_index: int) -> Dict[str, Any]:
    bounds = sprite.bounds() if hasattr(sprite, 'bounds') else {}
    return {
        'layer': layer_name,
        'layer_z': layer_z_index,
        'sprite_id': getattr(sprite, 'sprite_id', ''),
        'type': sprite.__class__.__name__,
        'semantic_role': getattr(sprite, 'semantic_role', ''),
        'z_index': getattr(sprite, 'z_index', ''),
        'rotation': getattr(sprite, 'rotation', ''),
        'scale': getattr(sprite, 'scale', ''),
        'bounds': _json_dump(bounds),
    }


def build_visualization_scene_debug_html(task: SessionTask) -> str:
    blueprint = build_visualization_blueprint(task)
    scene = build_visualization_scene(task)
    theme = blueprint.get('theme') or {}

    layer_rows: List[Dict[str, Any]] = []
    sprite_rows: List[Dict[str, Any]] = []
    z_rows: List[Dict[str, Any]] = []

    for layer in scene.layers:
        layer_rows.append(
            {
                'name': layer.name,
                'z_index': layer.z_index,
                'visibility': 'Sí' if layer.visibility else 'No',
                'opacity': layer.opacity,
                'sprites': len(layer.sprites),
            }
        )
        z_rows.append(
            {
                'name': layer.name,
                'z_index': layer.z_index,
                'sprite_count': len(layer.sprites),
            }
        )
        for sprite in layer.sprites:
            sprite_rows.append(_sprite_row(sprite, layer.name, layer.z_index))

    stats = [
        {'label': 'Task ID', 'value': task.id},
        {'label': 'Título', 'value': task.title or '-'},
        {'label': 'Theme', 'value': theme.get('key', '-')},
        {'label': 'Layers', 'value': len(scene.layers)},
        {'label': 'Sprites', 'value': len(scene.all_sprites())},
        {'label': 'Warnings', 'value': len(scene.warnings)},
    ]

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualization Scene Debug · Task {task.id}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #08111d;
      color: #e5e7eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: #0f172a;
      border: 1px solid rgba(148, 163, 184, .14);
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
    @media (max-width: 1200px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="stats">
    {''.join(f'<div class="stat"><small>{item["label"]}</small><strong>{item["value"]}</strong></div>' for item in stats)}
  </div>

  <div class="grid">
    <section class="card">
      <h2>Árbol de layers</h2>
      <div class="body">
        <table>
          <thead><tr><th>Layer</th><th>Z</th><th>Visible</th><th>Opacity</th><th>Sprites</th></tr></thead>
          <tbody>{_table_html(layer_rows, ['name', 'z_index', 'visibility', 'opacity', 'sprites'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Cámara</h2>
      <div class="body"><pre>{_json_dump(scene.camera)}</pre></div>
    </section>

    <section class="card">
      <h2>Iluminación</h2>
      <div class="body"><pre>{_json_dump(scene.lighting)}</pre></div>
    </section>

    <section class="card">
      <h2>Theme</h2>
      <div class="body"><pre>{_json_dump(theme)}</pre></div>
    </section>

    <section class="card wide">
      <h2>Sprites por layer</h2>
      <div class="body">
        <table>
          <thead>
            <tr>
              <th>Layer</th><th>Layer Z</th><th>Sprite ID</th><th>Type</th><th>Semantic role</th><th>Z</th><th>Rot</th><th>Scale</th><th>Bounds</th>
            </tr>
          </thead>
          <tbody>{_table_html(sprite_rows, ['layer', 'layer_z', 'sprite_id', 'type', 'semantic_role', 'z_index', 'rotation', 'scale', 'bounds'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Orden Z</h2>
      <div class="body">
        <table>
          <thead><tr><th>Layer</th><th>Z</th><th>Sprites</th></tr></thead>
          <tbody>{_table_html(z_rows, ['name', 'z_index', 'sprite_count'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Warnings</h2>
      <div class="body"><ul>{_list_html(scene.warnings)}</ul></div>
    </section>

    <section class="card wide">
      <h2>Visualization Scene</h2>
      <div class="body"><pre>{_json_dump(scene.as_dict())}</pre></div>
    </section>
  </div>
</body>
</html>"""


class Command(BaseCommand):
    help = 'Genera un HTML autónomo para inspeccionar la VisualizationScene de una tarea.'

    def add_arguments(self, parser):
        parser.add_argument('--task', type=int, required=True, help='ID de SessionTask.')
        parser.add_argument('--out', type=str, default='', help='Ruta opcional de salida para el HTML.')

    def handle(self, *args, **options):
        task_id = int(options['task'])
        out_raw = str(options.get('out') or '').strip()

        task = SessionTask.objects.select_related('session').filter(id=task_id).first()
        if not task:
            raise CommandError(f'No existe SessionTask #{task_id}.')

        out_path = Path(out_raw).expanduser() if out_raw else (Path.home() / 'Downloads' / 'visualization_scene_debug.html')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_visualization_scene_debug_html(task), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(str(out_path)))
