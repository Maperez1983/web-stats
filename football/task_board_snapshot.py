"""
FOTO HD de la pizarra de una tarea (ficha + PDF).

Misma receta que el snapshot de la pizarra de plantilla en los informes de dirección
(`_coach_pitch_board_snapshot_data_url`): en vez de recomponer la imagen por capas, **se fotografía
el DOM real** con Playwright a `device_scale_factor` alto y se guarda como JPEG.

Diferencia con el informe: allí las fichas se redibujan como HTML y basta con `set_content()`. Aquí
el dibujo lo genera Fabric con clases de token propias, así que reconstruirlo server-side produce
lienzos VACÍOS (es lo que vació ~75 miniaturas en la regeneración masiva). Por eso abrimos el
**editor real** de la tarea (`?embedded=1&snapshot=1`, que apaga todo el mueble del editor) y
fotografiamos `#task-pitch-stage`.

Por qué en un hilo aparte: en Render corremos con `WEB_CONCURRENCY=1`. Si el propio request se
quedase esperando a Playwright, el único worker estaría ocupado y no podría servir la página que
Playwright intenta abrir → interbloqueo. El request encola y responde al instante; el hilo hace la
foto cuando el worker ya está libre.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import threading

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.urls import reverse

logger = logging.getLogger(__name__)

try:  # Pillow es opcional en algunos entornos
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


# Viewport headless. Con dsf 2.0 la foto sale a ~3200 px de ancho (nítida en pantalla y en A4).
SNAPSHOT_VIEWPORT_WIDTH = 1600
SNAPSHOT_VIEWPORT_HEIGHT = 1000
SNAPSHOT_DEVICE_SCALE = 2.0
SNAPSHOT_SELECTOR = "#task-pitch-stage"
SNAPSHOT_READY_JS = "() => window.__WEBSTATS_TPAD_READY === true"

META_SIG_KEY = "board_hd_sig"

# Si un intento falla (sin Chromium, timeout, campo vacío), no reintentamos en cada visita.
FAIL_COOLDOWN_SECONDS = 30 * 60

# Tareas con foto en curso (evita lanzar N hilos para la misma tarea).
_inflight: set[int] = set()
_inflight_lock = threading.Lock()

# Un Chromium a la vez por proceso: abrir el editor completo consume bastante memoria y varias
# fichas abiertas a la vez podrían tumbar la instancia. Los demás esperan turno.
_render_gate = threading.Semaphore(1)
RENDER_GATE_TIMEOUT_SECONDS = 180


def board_signature(task) -> str:
    """Huella del DIBUJO. Si no cambia, la foto sigue valiendo.

    OJO con la estructura: el lienzo NO cuelga de la raiz de `tactical_layout`, sino de
    `meta.graphic_editor.canvas_state` (ver task_library_services.extract_canvas_state_for_preview).
    Mirar en la raiz devolvia siempre firma vacia y la foto no llegaba a encolarse nunca.
    """
    from .task_library_services import extract_canvas_state_for_preview

    layout = getattr(task, "tactical_layout", None) or {}
    if not isinstance(layout, dict):
        layout = {}
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}

    try:
        canvas_state, world_w, world_h = extract_canvas_state_for_preview(task)
    except Exception:
        canvas_state, world_w, world_h = None, 0, 0
    if not (isinstance(canvas_state, dict) and canvas_state.get("objects")):
        return ""

    parts = []
    try:
        parts.append(json.dumps(canvas_state, sort_keys=True, ensure_ascii=False))
    except Exception:
        parts.append(repr(canvas_state))
    parts.append(f"w={world_w}|h={world_h}")
    # La superficie tambien cambia la foto aunque no se mueva ninguna ficha.
    for key in ("pitch_preset", "pitch_orientation", "pitch_grass_style"):
        parts.append(f"{key}={meta.get(key)!r}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def stored_signature(task) -> str:
    layout = getattr(task, "tactical_layout", None) or {}
    if not isinstance(layout, dict):
        return ""
    meta = layout.get("meta")
    if not isinstance(meta, dict):
        return ""
    return str(meta.get(META_SIG_KEY) or "").strip()


SNAPSHOT_FILENAME_MARK = "board-hd"


def snapshot_is_current(task) -> bool:
    """True si `task_preview_image` YA es la foto HD del dibujo actual.

    Se comprueban DOS cosas: que la firma del dibujo no haya cambiado y que el fichero guardado sea
    de verdad una foto HD. Lo segundo importa porque cada guardado del editor sobrescribe
    `task_preview_image` con la captura de cliente (720 px); si solo mirásemos la firma, una tarea
    guardada sin tocar el dibujo se quedaría con la captura pequeña para siempre.
    """
    field = getattr(task, "task_preview_image", None)
    if not field:
        return False
    if SNAPSHOT_FILENAME_MARK not in str(getattr(field, "name", "") or ""):
        return False
    sig = board_signature(task)
    return bool(sig) and stored_signature(task) == sig


def session_cookies_for(request) -> list:
    """Cookies mínimas para que Playwright entre autenticado a nuestra propia app."""
    try:
        key = request.session.session_key
        if not key:
            request.session.save()
            key = request.session.session_key
    except Exception:
        key = ""
    if not key:
        return []
    base = request.build_absolute_uri("/")
    return [{
        "name": getattr(settings, "SESSION_COOKIE_NAME", "sessionid"),
        "value": str(key),
        "url": base,
    }]


def editor_snapshot_url(request, task) -> str:
    path = reverse("sessions-task-edit", args=[int(task.id)])
    query = "embedded=1&snapshot=1"
    team_id = getattr(getattr(getattr(task, "session", None), "team", None), "id", None)
    if team_id:
        query += f"&team={int(team_id)}"
    return request.build_absolute_uri(f"{path}?{query}")


def queue_snapshot(request, task, *, force: bool = False) -> bool:
    """Encola la foto HD si hace falta. No bloquea: devuelve enseguida."""
    if not getattr(settings, "TASK_BOARD_SNAPSHOT_ENABLED", True):
        return False
    try:
        task_id = int(getattr(task, "id", 0) or 0)
    except Exception:
        return False
    if not task_id:
        return False
    if not force and snapshot_is_current(task):
        return False
    sig = board_signature(task)
    if not sig:
        return False
    # Si el último intento falló, no volvemos a levantar Chromium en cada visita a la ficha.
    if not force and cache.get(_fail_key(task_id)):
        return False

    url = editor_snapshot_url(request, task)
    cookies = session_cookies_for(request)
    if not cookies:
        return False

    with _inflight_lock:
        if task_id in _inflight:
            return False
        _inflight.add(task_id)

    thread = threading.Thread(
        target=_render_and_store,
        args=(task_id, url, cookies, sig),
        name=f"board-snapshot-{task_id}",
        daemon=True,
    )
    thread.start()
    return True


def _fail_key(task_id: int) -> str:
    return f"task_board_hd:fail:{int(task_id)}"


def _last_error_key(task_id: int) -> str:
    return f"task_board_hd:last_error:{int(task_id)}"


def _note(task_id: int, message: str) -> None:
    try:
        cache.set(_last_error_key(task_id), str(message)[:400], 6 * 3600)
    except Exception:
        pass


def _mark_failed(task_id: int) -> None:
    try:
        cache.set(_fail_key(task_id), True, FAIL_COOLDOWN_SECONDS)
    except Exception:
        pass


def _render_and_store(task_id: int, url: str, cookies: list, sig: str) -> None:
    from django.db import connection

    try:
        png = _render(url, cookies)
        if not png:
            logger.warning("board snapshot: render vacio para tarea %s", task_id)
            _note(task_id, f"sin foto: Playwright no disponible o la pizarra no llego a estar lista · {url}")
            _mark_failed(task_id)
            return
        if not _looks_like_a_real_board(png):
            # Blindaje (mismo criterio que la regeneracion de miniaturas): si sale el campo pelado
            # sin fichas, NO pisamos la imagen buena que ya tenia la tarea.
            logger.warning("board snapshot: descartada (campo vacio) para tarea %s", task_id)
            _note(task_id, f"descartada: la foto sale como campo vacio (sin fichas) · {_stats_text(png)}")
            _mark_failed(task_id)
            return
        jpeg = _to_jpeg(png)
        _store(task_id, jpeg, sig)
        _note(task_id, f"ok · {len(jpeg)} bytes")
    except Exception as exc:
        logger.exception("board snapshot: fallo en tarea %s", task_id)
        _note(task_id, f"{type(exc).__name__}: {exc}")
        _mark_failed(task_id)
    finally:
        with _inflight_lock:
            _inflight.discard(task_id)
        try:
            connection.close()
        except Exception:
            pass


def _render(url: str, cookies: list) -> bytes | None:
    if not _render_gate.acquire(timeout=RENDER_GATE_TIMEOUT_SECONDS):
        logger.warning("board snapshot: cola llena, se salta esta foto")
        return None
    try:
        return _render_locked(url, cookies)
    finally:
        _render_gate.release()


def _render_locked(url: str, cookies: list) -> bytes | None:
    from .preview_render import render_url_selector_png

    return render_url_selector_png(
        url=url,
        selector=SNAPSHOT_SELECTOR,
        cookies=cookies,
        viewport_width=SNAPSHOT_VIEWPORT_WIDTH,
        viewport_height=SNAPSHOT_VIEWPORT_HEIGHT,
        device_scale_factor=SNAPSHOT_DEVICE_SCALE,
        wait_for_js=SNAPSHOT_READY_JS,
        timeout_ms=60000,
        settle_ms=1500,
    )


def _stats_text(png_bytes: bytes) -> str:
    from .task_library_services import analyze_preview_image_bytes

    stats = analyze_preview_image_bytes(png_bytes) or {}
    if not stats:
        return "sin metricas"
    return (
        f"{stats.get('width')}x{stats.get('height')} "
        f"verde={float(stats.get('green_ratio') or 0):.2f} "
        f"blanco={float(stats.get('white_ratio') or 0):.2f} "
        f"oscuro={float(stats.get('dark_ratio') or 0):.2f}"
    )


def _looks_like_a_real_board(png_bytes: bytes) -> bool:
    from .task_library_services import analyze_preview_image_bytes

    stats = analyze_preview_image_bytes(png_bytes)
    if not stats:
        return True  # sin Pillow no podemos juzgar: no bloqueamos
    try:
        green = float(stats.get("green_ratio") or 0.0)
        white = float(stats.get("white_ratio") or 0.0)
        dark = float(stats.get("dark_ratio") or 0.0)
    except Exception:
        return True
    return not (green >= 0.88 and white <= 0.18 and dark <= 0.35)


def _to_jpeg(png_bytes: bytes) -> bytes:
    if Image is None:
        return png_bytes
    try:
        with Image.open(io.BytesIO(png_bytes)) as shot:
            shot = shot.convert("RGB")
            buf = io.BytesIO()
            shot.save(buf, format="JPEG", quality=90, optimize=True, progressive=True)
        return buf.getvalue()
    except Exception:
        return png_bytes


def _store(task_id: int, image_bytes: bytes, sig: str) -> None:
    from .models import SessionTask

    task = SessionTask.objects.filter(pk=task_id).first()
    if not task:
        return
    # Si el usuario ha vuelto a dibujar mientras hacíamos la foto, la firma ya no cuadra:
    # descartamos esta foto (el siguiente guardado disparará otra).
    if board_signature(task) != sig:
        return

    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta[META_SIG_KEY] = sig
    layout["meta"] = meta
    task.tactical_layout = layout

    ext = "jpg" if image_bytes[:2] == b"\xff\xd8" else "png"
    task.task_preview_image.save(f"task-{task_id}-board-hd.{ext}", ContentFile(image_bytes), save=False)
    task.save(update_fields=["task_preview_image", "tactical_layout"])


def snapshot_data_uri(task) -> str:
    """Data URI de la foto guardada (para el PDF, que no puede pedir URLs autenticadas)."""
    field = getattr(task, "task_preview_image", None)
    if not field:
        return ""
    try:
        field.open("rb")
        try:
            raw = field.read() or b""
        finally:
            field.close()
    except Exception:
        return ""
    if not raw:
        return ""
    mime = "image/jpeg" if raw[:2] == b"\xff\xd8" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------------------
# Diagnóstico (coach-gated). Patrón que ya nos sirvió con Playwright en Render: si algo
# server-side "cae siempre al fallback", hace falta un endpoint que devuelva el error REAL.
# ---------------------------------------------------------------------------
def board_snapshot_status_view(request, task_id):
    from django.http import JsonResponse

    from .models import SessionTask
    from .permissions import can_access_sessions_workspace

    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    task = SessionTask.objects.filter(pk=int(task_id)).first()
    if not task:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    if str(request.GET.get("shot") or "").strip() in {"1", "true", "yes"}:
        # Diagnostico: renderiza AHORA y devuelve el PNG en crudo (no guarda nada). Sirve para ver
        # con los ojos que esta fotografiando Playwright cuando el blindaje la rechaza.
        from django.http import HttpResponse

        png = _render(editor_snapshot_url(request, task), session_cookies_for(request))
        if not png:
            return JsonResponse({"ok": False, "error": "sin foto (Playwright o pizarra no lista)"}, status=503)
        resp = HttpResponse(png, content_type="image/png")
        resp["X-Board-Stats"] = _stats_text(png)
        resp["Cache-Control"] = "no-store"
        return resp

    force = str(request.GET.get("force") or "").strip() in {"1", "true", "yes"}
    if force:
        try:
            cache.delete(_fail_key(int(task.id)))
        except Exception:
            pass
    queued = queue_snapshot(request, task, force=force)

    field = getattr(task, "task_preview_image", None)
    return JsonResponse({
        "ok": True,
        "task": int(task.id),
        "is_current": snapshot_is_current(task),
        "signature": board_signature(task),
        "stored_signature": stored_signature(task),
        "image": str(getattr(field, "name", "") or ""),
        "queued": bool(queued),
        "inflight": int(task.id) in _inflight,
        "cooldown": bool(cache.get(_fail_key(int(task.id)))),
        "last_note": cache.get(_last_error_key(int(task.id))) or "",
        "url": editor_snapshot_url(request, task),
    })
