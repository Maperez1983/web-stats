#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_HTML = TMP_DIR / "assets_catalog.html"
OUTPUT_JSON = TMP_DIR / "assets_catalog_selection.json"

CANDIDATES = [
    ROOT / "football/static",
    ROOT / "static",
    ROOT / "media",
    ROOT / "football/visualization_engine/assets_library",
    ROOT / "football/assets_library",
]

EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".glb",
    ".gltf",
    ".obj",
    ".mtl",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".pdf",
}

CATEGORIES = [
    "Players",
    "Goalkeepers",
    "Balls",
    "Cones",
    "Goals",
    "Arrows",
    "Grass",
    "Stadiums",
    "Shadows",
    "Icons",
    "Logos",
    "Textures",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def category_for(path: Path) -> str | None:
    value = rel(path).lower()
    name = path.name.lower()
    if "token-sprites/premium-goalkeeper" in value or "/goalkeepers/" in value:
        return "Goalkeepers"
    if (
        "/players/" in value
        or "token-sprites/premium-local" in value
        or "token-sprites/premium-rival" in value
        or "token-sprites/premium-blue" in value
        or "player-avatar" in value
        or "player_humanoid" in value
    ):
        return "Players"
    if "goal_premium" in value or "/goals/" in value or "/goal." in value or "/goal_" in value:
        return "Goals"
    if "ball" in name or "/balls/" in value:
        return "Balls"
    if "cone" in name or "/cones/" in value:
        return "Cones"
    if "arrow" in name or "/arrows/" in value:
        return "Arrows"
    if "shadow" in name or "/shadows/" in value:
        return "Shadows"
    if "grass" in name or "/grass/" in value or "surfaces/" in value:
        return "Grass"
    if "stadium" in name or "/stadiums/" in value or "pitch3d" in value or "seat" in name:
        return "Stadiums"
    if "/icons/" in value or "/drills/" in value:
        return "Icons"
    if "crest" in name or "logo" in name or "badge" in name or "/badges/" in value or "/logos/" in value:
        return "Logos"
    if (
        "/textures/" in value
        or "/materials/" in value
        or any(
            token in name
            for token in (
                "albedo",
                "normal",
                "roughness",
                "displacement",
                "ambientocclusion",
                "ao",
                "metalness",
                "opacity",
                "bump",
                "color",
            )
        )
    ):
        return "Textures"
    return None


def recommendation_for(path: Path, category: str) -> str:
    value = rel(path).lower()
    if value.startswith("media/"):
        return "descartar"
    if "/staticfiles/" in value:
        return "descartar"
    if category in {"Grass", "Stadiums", "Goals", "Textures"} and (
        path.suffix.lower() in {".glb", ".obj"} or "/materials/" in value or "/pitch3d/" in value
    ):
        return "enlazar"
    if category in {"Players", "Goalkeepers"} and "token-sprites/" in value:
        return "reutilizar"
    if category == "Players" and "/players/" in value:
        return "copiar"
    if category in {"Icons", "Logos"}:
        return "reutilizar"
    if category in {"Balls", "Cones", "Arrows", "Shadows"} and (
        "visualization_engine/assets_library" in value or "football/assets_library" in value
    ):
        return "reutilizar"
    if category == "Grass" and ("grass_premium" in value or "grass_uefa" in value):
        return "reutilizar"
    if category == "Stadiums" and path.suffix.lower() in {".png", ".svg"}:
        return "reutilizar"
    return "enlazar"


def quality_for(path: Path, category: str) -> str:
    value = rel(path).lower()
    if value.startswith("media/"):
        return "generado/referencia, no fuente maestra"
    if category == "Grass" and "grass_premium" in value:
        return "alta, base premium muy util"
    if category == "Stadiums" and "stadium_taskboard" in value:
        return "alta, ya coherente con el sistema visual"
    if category == "Stadiums" and path.suffix.lower() in {".glb", ".obj"}:
        return "alta para 3D, pesada pero valiosa"
    if category in {"Players", "Goalkeepers"} and "token-sprites" in value:
        return "media/alta, utilizable ya"
    if category == "Players" and "/players/" in value:
        return "media, específica de club"
    if category == "Icons":
        return "media/alta para UI e informes"
    if category == "Logos":
        return "alta para branding"
    if category == "Textures":
        return "alta, librería técnica reusable"
    if category in {"Balls", "Cones", "Arrows", "Shadows"}:
        return "placeholder o base funcional"
    return "media"


def file_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return f"{value:.1f} {units[index]}" if index else f"{int(value)} B"


def raster_meta(path: Path) -> tuple[str, str, str]:
    try:
        with Image.open(path) as image:
            width, height = image.size
            alpha = "sí" if ("A" in image.mode or "transparency" in image.info) else "no"
            return str(width), str(height), alpha
    except Exception:
        return "-", "-", "no"


def svg_meta(path: Path) -> tuple[str, str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        alpha = "sí" if (
            "opacity=" in text or "fill-opacity" in text or "stroke-opacity" in text or "transparent" in text
        ) else "sí"
        root = ET.fromstring(text)
        width = root.attrib.get("width")
        height = root.attrib.get("height")
        view_box = root.attrib.get("viewBox")
        if (not width or not height) and view_box:
            values = view_box.replace(",", " ").split()
            if len(values) == 4:
                width = values[2]
                height = values[3]
        return width or "vector", height or "vector", alpha
    except Exception:
        return "vector", "vector", "sí"


def meta_for(path: Path) -> tuple[str, str, str]:
    ext = path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
        return raster_meta(path)
    if ext == ".svg":
        return svg_meta(path)
    return "-", "-", "n/a"


def preview_html(path: Path) -> str:
    ext = path.suffix.lower()
    url = "file://" + str(path)
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}:
        return f'<img src="{html.escape(url)}" alt="{html.escape(path.name)}">'
    kind = {
        ".glb": "GLB",
        ".gltf": "GLTF",
        ".obj": "OBJ",
        ".mtl": "MTL",
        ".woff": "FONT",
        ".woff2": "FONT",
        ".ttf": "FONT",
        ".otf": "FONT",
        ".pdf": "PDF",
    }.get(ext, ext[1:].upper())
    return f'<div class="filebox">{html.escape(kind)}</div>'


def build_records() -> dict[str, list[dict[str, str]]]:
    records: dict[str, list[dict[str, str]]] = {category: [] for category in CATEGORIES}
    files: list[Path] = []
    for base in CANDIDATES:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXTS:
                continue
            if "/staticfiles/" in str(path):
                continue
            files.append(path)

    for path in sorted(files):
        category = category_for(path)
        if not category:
            continue
        width, height, alpha = meta_for(path)
        records[category].append(
            {
                "name": path.name,
                "path": rel(path),
                "format": path.suffix.lower().lstrip("."),
                "size": file_size(path.stat().st_size),
                "resolution": f"{width} x {height}" if width not in {"-", "vector"} else width,
                "alpha": alpha,
                "recommendation": recommendation_for(path, category),
                "quality": quality_for(path, category),
                "preview": preview_html(path),
            }
        )
    return records


def build_html(records: dict[str, list[dict[str, str]]]) -> str:
    formats = sorted({item["format"] for values in records.values() for item in values})
    category_options = "".join(
        f'<option value="{html.escape(category)}">{html.escape(category)}</option>' for category in CATEGORIES
    )
    format_options = "".join(
        f'<option value="{html.escape(asset_format)}">{html.escape(asset_format.upper())}</option>'
        for asset_format in formats
    )
    sections = []
    for category in CATEGORIES:
        entries = records.get(category, [])
        if entries:
            cards = []
            for item in entries:
                safe_path = html.escape(item["path"])
                cards.append(
                    f"""
<article class="card rec-{html.escape(item['recommendation'])}" data-category="{html.escape(category)}" data-format="{html.escape(item['format'])}" data-path="{safe_path}" data-filename="{html.escape(item['name'])}">
  <div class="preview">{item['preview']}</div>
  <div class="meta">
    <div class="head">
      <h3>{html.escape(item['name'])}</h3>
      <span class="badge badge-default">{html.escape(item['recommendation'])}</span>
    </div>
    <p class="path">{safe_path}</p>
    <ul>
      <li><strong>Tipo:</strong> {html.escape(category)}</li>
      <li><strong>Formato:</strong> {html.escape(item['format'])}</li>
      <li><strong>Tamaño:</strong> {html.escape(item['size'])}</li>
      <li><strong>Resolución:</strong> {html.escape(item['resolution'])}</li>
      <li><strong>Transparencia:</strong> {html.escape(item['alpha'])}</li>
      <li><strong>Calidad/utilidad:</strong> {html.escape(item['quality'])}</li>
      <li><strong>Recomendación inicial:</strong> {html.escape(item['recommendation'])}</li>
    </ul>
    <div class="decision-group">
      <button type="button" class="decision-btn accept" data-decision="accepted">Aceptar</button>
      <button type="button" class="decision-btn maybe" data-decision="maybe">Duda</button>
      <button type="button" class="decision-btn discard" data-decision="discarded">Descartar</button>
    </div>
    <label class="reason-box">
      <span>Motivo opcional</span>
      <textarea rows="2" placeholder="Anota aquí por qué lo aceptas, descartas o queda en duda."></textarea>
    </label>
  </div>
</article>
"""
                )
            body = "".join(cards)
        else:
            body = '<div class="empty">No se localizaron assets claros en esta categoría.</div>'
        sections.append(
            f'<section data-section-category="{html.escape(category)}"><h2>{html.escape(category)} <span>{len(entries)}</span></h2><div class="grid">{body}</div></section>'
        )

    data_blob = json.dumps(records, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assets Catalog</title>
<style>
:root {{
  --bg:#0b1220; --panel:#121a2b; --panel-2:#182235; --text:#e8eefc; --muted:#9fb0cf;
  --line:#26344d; --ok:#2ecc71; --warn:#f1c40f; --copy:#5dade2; --drop:#e57373;
  --accepted:#174c2c; --maybe:#574500; --discarded:#5b1f24; --default:#314562;
}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:linear-gradient(180deg,#0b1220,#0f1728);color:var(--text)}}
header{{position:sticky;top:0;z-index:10;padding:24px 28px;background:rgba(11,18,32,.94);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
header h1{{margin:0 0 8px;font-size:28px}}
header p{{margin:0;color:var(--muted)}}
.toolbar{{margin-top:18px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;align-items:end}}
.toolbar label{{display:grid;gap:6px;font-size:12px;color:var(--muted)}}
.toolbar select,.toolbar button{{width:100%;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:#11192a;color:var(--text);font:inherit}}
.toolbar button{{cursor:pointer;font-weight:700}}
.toolbar .wide{{grid-column:span 2}}
.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.summary span{{padding:6px 10px;border-radius:999px;border:1px solid var(--line);font-size:12px;color:var(--muted)}}
main{{padding:24px 28px 64px;display:flex;flex-direction:column;gap:28px}}
section h2{{margin:0 0 14px;font-size:22px;display:flex;gap:10px;align-items:center}}
section h2 span{{font-size:13px;color:var(--muted);padding:3px 8px;border:1px solid var(--line);border-radius:999px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(390px,1fr));gap:16px}}
.card{{display:grid;grid-template-columns:160px 1fr;gap:14px;padding:14px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(180deg,var(--panel),var(--panel-2));box-shadow:0 12px 30px rgba(0,0,0,.22)}}
.card[data-selection="accepted"]{{border-color:#2ecc71;background:linear-gradient(180deg,#112618,#173121)}}
.card[data-selection="maybe"]{{border-color:#f1c40f;background:linear-gradient(180deg,#2a250d,#302911)}}
.card[data-selection="discarded"]{{border-color:#e57373;background:linear-gradient(180deg,#2d1719,#341d20)}}
.preview{{height:160px;border-radius:14px;background:#0a0f1b;border:1px solid #24324c;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.preview img{{max-width:100%;max-height:100%;object-fit:contain;display:block}}
.filebox{{width:88px;height:88px;border-radius:18px;border:1px solid #304160;display:flex;align-items:center;justify-content:center;font-weight:800;letter-spacing:.08em;color:#dbe7ff;background:#12192a}}
.meta{{display:grid;gap:10px}}
.head{{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}}
.meta h3{{margin:0;font-size:16px;line-height:1.25}}
.path{{margin:0;font-size:11px;line-height:1.4;color:var(--muted);word-break:break-all}}
ul{{margin:0;padding-left:16px;display:grid;gap:4px;font-size:13px;color:#d8e2f5}}
li strong{{color:#fff}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid currentColor;font-weight:700;text-transform:capitalize}}
.badge-default{{color:#9fb0cf}}
.badge-accepted{{color:var(--ok)}}
.badge-maybe{{color:var(--warn)}}
.badge-discarded{{color:var(--drop)}}
.decision-group{{display:flex;gap:8px;flex-wrap:wrap}}
.decision-btn{{padding:8px 12px;border-radius:10px;border:1px solid var(--line);background:#12192a;color:var(--text);font-weight:700;cursor:pointer}}
.decision-btn.accept{{border-color:#2ecc71;color:#9df0bc}}
.decision-btn.maybe{{border-color:#f1c40f;color:#ffe38a}}
.decision-btn.discard{{border-color:#e57373;color:#ffb1b1}}
.reason-box{{display:grid;gap:6px;font-size:12px;color:var(--muted)}}
.reason-box textarea{{width:100%;resize:vertical;border-radius:10px;border:1px solid var(--line);background:#0e1626;color:var(--text);padding:10px;font:inherit}}
.empty{{padding:18px;border:1px dashed var(--line);border-radius:16px;color:var(--muted);background:rgba(255,255,255,.02)}}
.hidden{{display:none !important}}
</style>
</head>
<body>
<header>
  <h1>Catálogo visual de assets reutilizables</h1>
  <p>Revisión visual previa a decidir qué pasa a <code>assets_library</code>. No se modifica ningún asset real.</p>
  <div class="toolbar">
    <label>
      Estado
      <select id="filter-status">
        <option value="all">Todos</option>
        <option value="accepted">Aceptados</option>
        <option value="discarded">Descartados</option>
        <option value="maybe">Dudosos</option>
        <option value="unreviewed">Sin revisar</option>
      </select>
    </label>
    <label>
      Categoría
      <select id="filter-category">
        <option value="all">Todas</option>
        {category_options}
      </select>
    </label>
    <label>
      Formato
      <select id="filter-format">
        <option value="all">Todos</option>
        {format_options}
      </select>
    </label>
    <button type="button" id="download-json">Descargar selección JSON</button>
    <button type="button" id="copy-json">Copiar selección JSON</button>
  </div>
  <div class="summary">
    <span id="summary-total">Total: 0</span>
    <span id="summary-accepted">Aceptados: 0</span>
    <span id="summary-maybe">Dudosos: 0</span>
    <span id="summary-discarded">Descartados: 0</span>
    <span id="summary-unreviewed">Sin revisar: 0</span>
  </div>
</header>
<main>
  {''.join(sections)}
</main>
<script>
const STORAGE_KEY = 'webstats-assets-catalog-selection-v1';
const RAW_RECORDS = {data_blob};

function emptySelection() {{
  return {{ accepted: [], discarded: [], maybe: [] }};
}}

function normalizeEntry(entry) {{
  return {{
    path: entry.path,
    category: entry.category,
    filename: entry.filename,
    reason: entry.reason || ''
  }};
}}

function loadSelection() {{
  try {{
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!parsed || typeof parsed !== 'object') return emptySelection();
    return {{
      accepted: Array.isArray(parsed.accepted) ? parsed.accepted : [],
      discarded: Array.isArray(parsed.discarded) ? parsed.discarded : [],
      maybe: Array.isArray(parsed.maybe) ? parsed.maybe : [],
    }};
  }} catch (error) {{
    return emptySelection();
  }}
}}

function saveSelection(selection) {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selection, null, 2));
}}

function removePath(selection, path) {{
  for (const key of ['accepted', 'discarded', 'maybe']) {{
    selection[key] = selection[key].filter(item => item.path !== path);
  }}
}}

function getStatus(selection, path) {{
  if (selection.accepted.some(item => item.path === path)) return 'accepted';
  if (selection.discarded.some(item => item.path === path)) return 'discarded';
  if (selection.maybe.some(item => item.path === path)) return 'maybe';
  return 'unreviewed';
}}

function getReason(selection, path) {{
  for (const key of ['accepted', 'discarded', 'maybe']) {{
    const found = selection[key].find(item => item.path === path);
    if (found) return found.reason || '';
  }}
  return '';
}}

function setDecision(path, category, filename, decision, reason) {{
  const selection = loadSelection();
  removePath(selection, path);
  if (decision !== 'unreviewed') {{
    selection[decision].push(normalizeEntry({{ path, category, filename, reason }}));
  }}
  saveSelection(selection);
  syncUI();
}}

function setReason(path, reason) {{
  const selection = loadSelection();
  for (const key of ['accepted', 'discarded', 'maybe']) {{
    const found = selection[key].find(item => item.path === path);
    if (found) found.reason = reason;
  }}
  saveSelection(selection);
  syncUI();
}}

function filteredCards() {{
  const status = document.getElementById('filter-status').value;
  const category = document.getElementById('filter-category').value;
  const format = document.getElementById('filter-format').value;
  const selection = loadSelection();
  return Array.from(document.querySelectorAll('.card')).filter(card => {{
    const cardStatus = getStatus(selection, card.dataset.path);
    const okStatus = status === 'all' ? true : cardStatus === status;
    const okCategory = category === 'all' ? true : card.dataset.category === category;
    const okFormat = format === 'all' ? true : card.dataset.format === format;
    return okStatus && okCategory && okFormat;
  }});
}}

function syncSummary(selection) {{
  const cards = Array.from(document.querySelectorAll('.card'));
  const accepted = cards.filter(card => getStatus(selection, card.dataset.path) === 'accepted').length;
  const maybe = cards.filter(card => getStatus(selection, card.dataset.path) === 'maybe').length;
  const discarded = cards.filter(card => getStatus(selection, card.dataset.path) === 'discarded').length;
  const unreviewed = cards.length - accepted - maybe - discarded;
  document.getElementById('summary-total').textContent = `Total: ${{cards.length}}`;
  document.getElementById('summary-accepted').textContent = `Aceptados: ${{accepted}}`;
  document.getElementById('summary-maybe').textContent = `Dudosos: ${{maybe}}`;
  document.getElementById('summary-discarded').textContent = `Descartados: ${{discarded}}`;
  document.getElementById('summary-unreviewed').textContent = `Sin revisar: ${{unreviewed}}`;
}}

function syncVisibility() {{
  const visible = new Set(filteredCards().map(card => card.dataset.path));
  document.querySelectorAll('.card').forEach(card => {{
    card.classList.toggle('hidden', !visible.has(card.dataset.path));
  }});
  document.querySelectorAll('section[data-section-category]').forEach(section => {{
    const cards = section.querySelectorAll('.card:not(.hidden)');
    section.classList.toggle('hidden', cards.length === 0);
  }});
}}

function syncUI() {{
  const selection = loadSelection();
  document.querySelectorAll('.card').forEach(card => {{
    const path = card.dataset.path;
    const status = getStatus(selection, path);
    card.dataset.selection = status;
    const badge = card.querySelector('.badge');
    badge.className = 'badge';
    if (status === 'accepted') {{
      badge.classList.add('badge-accepted');
      badge.textContent = 'accepted';
    }} else if (status === 'maybe') {{
      badge.classList.add('badge-maybe');
      badge.textContent = 'maybe';
    }} else if (status === 'discarded') {{
      badge.classList.add('badge-discarded');
      badge.textContent = 'discarded';
    }} else {{
      badge.classList.add('badge-default');
      badge.textContent = 'sin revisar';
    }}
    const textarea = card.querySelector('textarea');
    if (textarea !== document.activeElement) {{
      textarea.value = getReason(selection, path);
    }}
  }});
  syncSummary(selection);
  syncVisibility();
}}

function currentSelectionJson() {{
  return JSON.stringify(loadSelection(), null, 2);
}}

document.querySelectorAll('.decision-btn').forEach(button => {{
  button.addEventListener('click', () => {{
    const card = button.closest('.card');
    const textarea = card.querySelector('textarea');
    setDecision(card.dataset.path, card.dataset.category, card.dataset.filename, button.dataset.decision, textarea.value.trim());
  }});
}});

document.querySelectorAll('.reason-box textarea').forEach(textarea => {{
  textarea.addEventListener('change', () => {{
    const card = textarea.closest('.card');
    setReason(card.dataset.path, textarea.value.trim());
  }});
}});

document.getElementById('filter-status').addEventListener('change', syncUI);
document.getElementById('filter-category').addEventListener('change', syncUI);
document.getElementById('filter-format').addEventListener('change', syncUI);

document.getElementById('download-json').addEventListener('click', () => {{
  const blob = new Blob([currentSelectionJson()], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'assets_catalog_selection.json';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}});

document.getElementById('copy-json').addEventListener('click', async () => {{
  const payload = currentSelectionJson();
  try {{
    await navigator.clipboard.writeText(payload);
    const button = document.getElementById('copy-json');
    const previous = button.textContent;
    button.textContent = 'JSON copiado';
    setTimeout(() => {{ button.textContent = previous; }}, 1200);
  }} catch (error) {{
    alert('No se pudo copiar automáticamente. Usa el botón de descarga JSON.');
  }}
}});

syncUI();
</script>
</body>
</html>
"""


def main() -> None:
    records = build_records()
    OUTPUT_HTML.write_text(build_html(records), encoding="utf-8")
    OUTPUT_JSON.write_text(json.dumps({"accepted": [], "discarded": [], "maybe": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(OUTPUT_HTML)
    print(OUTPUT_JSON)


if __name__ == "__main__":
    main()
