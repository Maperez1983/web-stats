from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from django.core.management.base import BaseCommand


LIBRARY_ROOT = Path(__file__).resolve().parents[2] / 'assets_library'


def _read_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def _tree_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for category_dir in sorted([path for path in LIBRARY_ROOT.iterdir() if path.is_dir()]):
        manifest = _read_manifest(category_dir / 'manifest.json')
        rows.append(
            {
                'category': category_dir.name,
                'category_type': manifest.get('category_type', '-'),
                'default_family': manifest.get('default_family', '-'),
                'families': ', '.join(manifest.get('families', [])) or '-',
                'variants': ', '.join(manifest.get('variants', [])) or '-',
                'fallback': manifest.get('fallback_asset', '-') or '-',
                'themes': ', '.join(manifest.get('compatible_themes', [])) or '-',
            }
        )
    return rows


def build_assets_library_debug_html() -> str:
    rows = _tree_rows()
    tree_lines = '\n'.join(
        f'football/assets_library/{row["category"]}/\n  ├─ manifest.json\n  └─ README.md'
        for row in rows
    )
    manifest_dump = json.dumps(
        {row['category']: _read_manifest(LIBRARY_ROOT / row['category'] / 'manifest.json') for row in rows},
        ensure_ascii=False,
        indent=2,
    )
    table_rows = ''.join(
        (
            '<tr>'
            f'<td>{row["category"]}</td>'
            f'<td>{row["category_type"]}</td>'
            f'<td>{row["default_family"]}</td>'
            f'<td>{row["families"]}</td>'
            f'<td>{row["variants"]}</td>'
            f'<td>{row["fallback"]}</td>'
            f'<td>{row["themes"]}</td>'
            '</tr>'
        )
        for row in rows
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assets Library Debug</title>
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
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}
    .card {{
      background: #111827;
      border: 1px solid rgba(148,163,184,.15);
      border-radius: 16px;
      overflow: hidden;
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 18px;
      background: #0f172a;
      font-size: 17px;
    }}
    .body {{
      padding: 16px 18px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: #cbd5e1;
      font-size: 12px;
      line-height: 1.5;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 8px 10px;
      border-bottom: 1px solid rgba(148,163,184,.12);
    }}
    th {{
      color: #93c5fd;
    }}
    .wide {{
      grid-column: 1 / -1;
    }}
    @media (max-width: 1200px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="grid">
    <section class="card">
      <h2>Árbol completo</h2>
      <div class="body"><pre>{tree_lines}</pre></div>
    </section>
    <section class="card">
      <h2>Familias, variantes, fallbacks y themes compatibles</h2>
      <div class="body">
        <table>
          <thead>
            <tr>
              <th>Categoría</th>
              <th>Tipo</th>
              <th>Familia por defecto</th>
              <th>Familias</th>
              <th>Variantes</th>
              <th>Fallback</th>
              <th>Themes</th>
            </tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>
    </section>
    <section class="card wide">
      <h2>Manifest completo</h2>
      <div class="body"><pre>{manifest_dump}</pre></div>
    </section>
  </div>
</body>
</html>"""


class Command(BaseCommand):
    help = 'Genera un HTML de diagnóstico de la assets library.'

    def handle(self, *args, **options):
        output_path = Path.home() / 'Downloads' / 'assets_library_debug.html'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build_assets_library_debug_html(), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(str(output_path)))
