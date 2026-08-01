from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.core.management.base import BaseCommand, CommandError

from football.models import SessionTask
from football.visualization_engine import (
    build_visualization_blueprint,
    build_visualization_composition,
)
from football.visualization_engine.composition.composer import build_basic_composition_preview_svg


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


def _pick_task(task_id: int | None) -> SessionTask:
    if task_id:
        task = SessionTask.objects.select_related('session').filter(id=task_id).first()
        if not task:
            raise CommandError(f'No existe SessionTask #{task_id}.')
        return task
    fallback = SessionTask.objects.filter(title__icontains='[DIAG] Render Engine Test').order_by('-id').first()
    if fallback:
        return fallback
    latest = SessionTask.objects.order_by('-id').first()
    if not latest:
        raise CommandError('No hay SessionTask disponibles para diagnóstico.')
    return latest


def build_visualization_composition_debug_html(task: SessionTask) -> str:
    blueprint = build_visualization_blueprint(task, theme_key='premium')
    composition_scene = build_visualization_composition(task, theme_key='premium')
    registry = blueprint.get('asset_registry')
    manifest = registry.manifest_for('premium').as_dict() if registry else {'theme_key': 'premium', 'assets': []}

    layer_rows = [
        {
            'name': layer.name,
            'z_index': layer.z_index,
            'visible': 'Sí' if layer.visibility else 'No',
            'opacity': layer.opacity,
            'items': len(layer.items),
        }
        for layer in composition_scene.layers
    ]
    binding_rows = [binding.as_dict() for binding in composition_scene.bindings]
    asset_rows = list(composition_scene.assets_used)
    preview_svg = build_basic_composition_preview_svg(composition_scene)

    stats = [
        {'label': 'Task ID', 'value': task.id},
        {'label': 'Título', 'value': task.title or '-'},
        {'label': 'Theme', 'value': ((blueprint.get('theme') or {}).get('key') or '-')},
        {'label': 'Sprites', 'value': len(blueprint.get('sprites') or [])},
        {'label': 'Bindings', 'value': len(composition_scene.bindings)},
        {'label': 'Assets', 'value': len(composition_scene.assets_used)},
    ]

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualization Composition Debug · Task {task.id}</title>
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
    .preview {{
      background: #020617;
      border-radius: 16px;
      overflow: auto;
      padding: 12px;
    }}
    .preview svg {{ max-width: 100%; height: auto; display: block; }}
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
    <section class="card wide">
      <h2>Preview visual básica de la composición</h2>
      <div class="body preview">{preview_svg}</div>
    </section>

    <section class="card">
      <h2>Assets usados</h2>
      <div class="body">
        <table>
          <thead><tr><th>Asset ID</th><th>Tipo</th><th>Source</th></tr></thead>
          <tbody>{_table_html(asset_rows, ['asset_id', 'asset_type', 'source'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Warnings</h2>
      <div class="body"><ul>{_list_html(composition_scene.warnings)}</ul></div>
    </section>

    <section class="card">
      <h2>Capas de composición</h2>
      <div class="body">
        <table>
          <thead><tr><th>Layer</th><th>Z</th><th>Visible</th><th>Opacity</th><th>Items</th></tr></thead>
          <tbody>{_table_html(layer_rows, ['name', 'z_index', 'visible', 'opacity', 'items'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Asset Registry / Manifest</h2>
      <div class="body"><pre>{_json_dump(manifest)}</pre></div>
    </section>

    <section class="card wide">
      <h2>Sprites vinculados a assets</h2>
      <div class="body">
        <table>
          <thead>
            <tr>
              <th>Sprite ID</th><th>Type</th><th>Layer</th><th>Asset ID</th><th>Role</th><th>X</th><th>Y</th><th>Rot</th><th>Scale</th><th>Z</th><th>Warnings</th>
            </tr>
          </thead>
          <tbody>{_table_html(binding_rows, ['sprite_id', 'sprite_type', 'layer_name', 'asset_id', 'semantic_role', 'x', 'y', 'rotation', 'scale', 'z_index', 'warnings'])}</tbody>
        </table>
      </div>
    </section>

    <section class="card wide">
      <h2>Composition Scene</h2>
      <div class="body"><pre>{_json_dump(composition_scene.as_dict())}</pre></div>
    </section>
  </div>
</body>
</html>"""


class Command(BaseCommand):
    help = 'Genera un HTML autónomo para inspeccionar la composición basada en assets de una tarea.'

    def add_arguments(self, parser):
        parser.add_argument('--task', type=int, required=False, help='ID de SessionTask.')
        parser.add_argument('--out', type=str, default='', help='Ruta opcional de salida para el HTML.')

    def handle(self, *args, **options):
        task = _pick_task(options.get('task'))
        out_raw = str(options.get('out') or '').strip()
        out_path = Path(out_raw).expanduser() if out_raw else (Path.home() / 'Downloads' / 'visualization_composition_debug.html')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_visualization_composition_debug_html(task), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(str(out_path)))
