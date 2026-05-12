from __future__ import annotations

import base64
import json
import mimetypes
import os
import contextlib
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings


# Render: ensure Playwright browsers are looked up from the "hermetic" install location (bundled with
# the app) instead of a per-user cache that may not persist between build/runtime or across instances.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


def shutdown_preview_renderer() -> None:
    """
    Best-effort shutdown for Playwright resources.

    Nota: este módulo ya no mantiene un navegador global (para evitar que el loop interno de
    Playwright contamine el hilo del worker y dispare `SynchronousOnlyOperation` en Django).
    """
    return None


def _guess_mime(path_or_url: str) -> str:
    mime, _ = mimetypes.guess_type(path_or_url)
    return mime or "application/octet-stream"


def _static_candidates_for_url(url: str) -> list[Path]:
    raw = str(url or "").strip()
    if not raw:
        return []
    if raw.startswith("data:"):
        return []
    if raw.startswith("http://") or raw.startswith("https://"):
        return []
    rel = raw
    if rel.startswith("/"):
        rel = rel[1:]
    # Most image URLs come as "static/..." or "/static/...".
    if rel.startswith("static/"):
        rel = rel[len("static/") :]
    # STATIC_ROOT first (collected), then dev static dirs.
    candidates: list[Path] = []
    try:
        candidates.append(Path(settings.STATIC_ROOT) / rel)
    except Exception:
        pass
    try:
        for base in getattr(settings, "STATICFILES_DIRS", []) or []:
            candidates.append(Path(base) / rel)
    except Exception:
        pass
    return candidates


def _media_candidates_for_url(url: str) -> list[Path]:
    raw = str(url or "").strip()
    if not raw:
        return []
    if raw.startswith("data:"):
        return []
    if raw.startswith("http://") or raw.startswith("https://"):
        return []
    rel = raw
    if rel.startswith("/"):
        rel = rel[1:]
    # "media/..." or "/media/..."
    if rel.startswith("media/"):
        rel = rel[len("media/") :]
    candidates: list[Path] = []
    try:
        candidates.append(Path(settings.MEDIA_ROOT) / rel)
    except Exception:
        pass
    return candidates


def _url_to_data_url(url: str) -> str | None:
    raw = str(url or "").strip()
    if not raw or raw.startswith("data:"):
        return None
    candidates: list[Path] = []

    path_hint = raw
    if raw.startswith("http://") or raw.startswith("https://"):
        try:
            parsed = urlparse(raw)
            if parsed and parsed.path:
                path_hint = parsed.path
        except Exception:
            path_hint = raw

    if "/static/" in path_hint or path_hint.startswith("/static/") or path_hint.startswith("static/"):
        candidates.extend(_static_candidates_for_url(path_hint))
    if "/media/" in path_hint or path_hint.startswith("/media/") or path_hint.startswith("media/"):
        candidates.extend(_media_candidates_for_url(path_hint))
    for path in candidates:
        try:
            if not path.exists() or not path.is_file():
                continue
            content = path.read_bytes()
            mime = _guess_mime(str(path))
            payload = base64.b64encode(content).decode("ascii")
            return f"data:{mime};base64,{payload}"
        except Exception:
            continue
    return None


def _rewrite_urls_to_data_urls(payload):
    if isinstance(payload, dict):
        for key, value in list(payload.items()):
            if isinstance(value, str) and key.lower() in {"src", "url", "href"}:
                replaced = _url_to_data_url(value)
                if replaced:
                    payload[key] = replaced
                    continue
            payload[key] = _rewrite_urls_to_data_urls(value)
        return payload
    if isinstance(payload, list):
        return [_rewrite_urls_to_data_urls(item) for item in payload]
    return payload


@contextlib.contextmanager
def _acquire_playwright_browser():
    """
    Crea un browser de Playwright y lo cierra al salir.

    Importante: NO mantenemos Playwright "vivo" entre requests. Su Sync API usa un loop interno
    y, si queda activo en el hilo del worker, Django puede lanzar `SynchronousOnlyOperation`
    al acceder a ORM/sesiones en ese mismo hilo.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        yield None, None
        return

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(args=["--no-sandbox"])
        yield pw, browser
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass


def render_task_preview_png(
    *,
    canvas_state: dict,
    pitch_preset: str = "full_pitch",
    pitch_orientation: str = "landscape",
    pitch_grass_style: str = "classic",
    pitch_zoom: float = 1.0,
    world_width: int = 1280,
    world_height: int = 720,
    max_side: int = 4096,
) -> bytes | None:
    """
    Render WYSIWYG tactical board preview using Playwright + Fabric.
    Returns PNG bytes or None when Playwright/browsers aren't available.
    """
    if not isinstance(canvas_state, dict):
        return None
    pw = None
    browser = None

    orientation = "portrait" if str(pitch_orientation).strip().lower() == "portrait" else "landscape"
    preset = str(pitch_preset or "full_pitch").strip() or "full_pitch"
    grass_style = str(pitch_grass_style or "classic").strip().lower()
    if grass_style not in {"classic", "broadcast", "realistic", "pro", "artificial", "dry", "wet", "uefa_b", "whiteboard", "blackboard"}:
        grass_style = "classic"
    try:
        zoom = float(pitch_zoom or 1.0)
    except Exception:
        zoom = 1.0
    zoom = max(0.8, min(zoom, 1.6))
    world_width = max(320, min(int(world_width or 1280), 3840))
    world_height = max(180, min(int(world_height or 720), 2160))

    # Target stage ratio 105x68, swapped in portrait.
    ratio = 105 / 68
    if orientation == "portrait":
        target_h = int(max_side)
        target_w = int(round(target_h / ratio))
    else:
        target_w = int(max_side)
        target_h = int(round(target_w / ratio))

    # Use deviceScaleFactor to get crisp output without huge layout sizes.
    dpr = 2
    viewport_w = max(640, int(round(target_w / dpr)))
    viewport_h = max(480, int(round(target_h / dpr)))

    # Inline local static/media images to avoid self-HTTP deadlocks on single-worker deploys.
    safe_state = json.loads(json.dumps(canvas_state, ensure_ascii=False))
    safe_state = _rewrite_urls_to_data_urls(safe_state)

    grass_tiles = {}
    if grass_style == "uefa_b":
        try:
            tile_path = Path(settings.BASE_DIR) / "football" / "static" / "football" / "images" / "surfaces" / "grass_uefa_b_tile.png"
            if tile_path.exists():
                grass_tiles["uefa_b"] = "data:image/png;base64," + base64.b64encode(tile_path.read_bytes()).decode("ascii")
        except Exception:
            grass_tiles = {}

    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: #2f7d32;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    #stage {{
      position: relative;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background: #2f7d32;
    }}
    #pitch {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    #pitch svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    #c {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
	<body>
	  <div id="stage">
	    <div id="pitch"></div>
	    <canvas id="c"></canvas>
	  </div>

	  <script>
	    window.__WEBSTATS_GRASS_TILES = {json.dumps(grass_tiles, ensure_ascii=False)};
	  </script>
	  <script>
		    window.__TPAD_RENDER__ = {json.dumps({
		        "preset": preset,
		        "orientation": orientation,
		        "grass_style": grass_style,
	        "zoom": zoom,
	        "world": {"w": world_width, "h": world_height},
	        "state": safe_state,
	    }, ensure_ascii=False)};
  </script>
</body>
</html>
"""

    # JS snippet: pitch SVG builder extracted from sessions_tactical_pad.js
    js_path = Path(settings.BASE_DIR) / "football" / "static" / "football" / "js" / "sessions_tactical_pad.js"
    pitch_snippet = ""
    try:
        lines = js_path.read_text(encoding="utf-8").splitlines()
        # Extraemos el builder del césped/campo desde el principio del archivo hasta antes del init del editor.
        # Evita depender de offsets fijos (el fichero crece a menudo con nuevas funciones).
        end = None
        for idx, line in enumerate(lines):
            if "window.initSessionsTacticalPad" in line:
                end = idx
                break
        if end is None:
            end = min(len(lines), 900)
        start = 0
        # El fichero está envuelto en una IIFE: evitamos incluir la línea de apertura
        # para no dejar llaves sin cerrar en este snippet.
        if lines and lines[0].lstrip().startswith("(function"):
            start = 1
        snippet_lines = lines[start:end]
        pitch_snippet = "\n".join(snippet_lines) + "\nwindow.__buildPitchSvg = buildPitchSvg;"
    except Exception:
        pitch_snippet = ""

    fabric_path = Path(settings.BASE_DIR) / "football" / "static" / "vendor" / "fabric.min.js"
    if not fabric_path.exists():
        # Fallback: static directory might be collected.
        fabric_path = Path(settings.STATIC_ROOT) / "vendor" / "fabric.min.js"

    with _acquire_playwright_browser() as (pw, browser):
        if not pw or not browser:
            return None
        context = None
        try:
            context = browser.new_context(
                viewport={"width": int(viewport_w), "height": int(viewport_h)},
                device_scale_factor=float(dpr),
            )
            page = context.new_page()
            # Avoid external network hangs when Fabric tries to load remote images.
            # We inline local /static and /media URLs into data: URLs before rendering.
            # Any other remote requests are aborted quickly.
            try:
                page.route("**/*", lambda route: route.abort() if route.request.url.startswith(("http://", "https://")) else route.continue_())
            except Exception:
                pass
            page.set_content(html, wait_until="load")

            if fabric_path.exists():
                page.add_script_tag(path=str(fabric_path))
            if pitch_snippet:
                page.add_script_tag(content=f"(function(){{\n{pitch_snippet}\n}})();")

            page.add_script_tag(
                content="""
              (async () => {
                const cfg = window.__TPAD_RENDER__ || {};
	                const preset = String(cfg.preset || 'full_pitch');
	                const orientation = String(cfg.orientation || 'landscape') === 'portrait' ? 'portrait' : 'landscape';
		                const rawGrass = String(cfg.grass_style || 'classic').trim().toLowerCase();
		                const grassStyle = ['classic', 'broadcast', 'realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'whiteboard', 'blackboard'].includes(rawGrass) ? rawGrass : 'classic';
	                const zoom = Number(cfg.zoom || 1);
	                const world = cfg.world || {};
	                const state = cfg.state || {};

                const stage = document.getElementById('stage');
                const pitch = document.getElementById('pitch');
                const canvasEl = document.getElementById('c');

	                try {
	                  const svgMarkup = (window.__buildPitchSvg ? window.__buildPitchSvg(preset, orientation, grassStyle) : '');
	                  pitch.innerHTML = svgMarkup || '';
	                } catch (e) {
	                  pitch.innerHTML = '';
	                }

                const rect = stage.getBoundingClientRect();
                const width = Math.max(320, Math.round(rect.width || 1280));
                const height = Math.max(220, Math.round(rect.height || 720));

                const canvas = new fabric.StaticCanvas(canvasEl, {
                  preserveObjectStacking: true,
                  selection: false,
                  enableRetinaScaling: false,
                });
                canvas.setDimensions({ width, height });

                const fromW = Math.max(1, Number(world.w || 1280));
                const fromH = Math.max(1, Number(world.h || 720));
                const baseScale = Math.min(width / fromW, height / fromH);
                const scale = baseScale * Math.max(0.8, Math.min(zoom || 1, 1.6));
                const scaledW = fromW * scale;
                const scaledH = fromH * scale;
                const offsetX = (width - scaledW) / 2;
                const offsetY = (height - scaledH) / 2;
                canvas.setViewportTransform([scale, 0, 0, scale, offsetX, offsetY]);

                const doRender = () => {
                  try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
                  window.__render_done = true;
                };

                try {
                  const payload = { version: state.version || '5.3.0', objects: Array.isArray(state.objects) ? state.objects : [] };
                  const p = canvas.loadFromJSON(payload, doRender);
                  if (p && typeof p.then === 'function') await p;
                  else {
                    // loadFromJSON callback already calls doRender.
                  }
                } catch (e) {
                  doRender();
                }
              })();
            """,
            )

            page.wait_for_function("window.__render_done === true", timeout=15000)
            # Capture stage (pitch + overlay) at device scale.
            png_bytes = page.locator("#stage").screenshot(type="png")
            try:
                context.close()
            except Exception:
                pass
            return png_bytes
        except Exception:
            try:
                if context:
                    context.close()
            except Exception:
                pass
            return None
