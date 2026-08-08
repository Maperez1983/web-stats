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
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils import timezone

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
SNAPSHOT_READY_JS = "() => window.__WEBSTATS_SNAPSHOT_READY === true"

META_SIG_KEY = "board_hd_sig"

# Un Chromium a la vez por proceso. Queda para el diagnóstico `?shot=1`, que sí renderiza dentro
# del web; las fotos de verdad las hace `manage.py fotos_pizarra` en su propio proceso, de una en
# una, y por eso ya no compiten con la app que tiene que servirles la página del editor.
_render_gate = threading.Semaphore(1)
RENDER_GATE_TIMEOUT_SECONDS = 900

# Tiempo de espera del navegador, en función de lo cargado que esté el dibujo (ver `_timeouts_for`).
# 60 s se quedaban cortos: el log lleva desde el 2 de agosto repitiendo "render vacio" en tareas
# de 12-19 objetos, que no son pesadas. La pagina del editor es grande y en el contenedor arranca
# despacio, asi que el suelo sube a 90 s. Lo que cuesta un fallo aqui es una tarjeta en verde
# durante horas; lo que cuesta esperar 30 s mas es nada, porque la foto va en segundo plano.
SNAPSHOT_TIMEOUT_BASE_MS = 90000
SNAPSHOT_TIMEOUT_PER_OBJECT_MS = 180
SNAPSHOT_TIMEOUT_MAX_MS = 240000


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


def editor_snapshot_url_for(task, base_url: str) -> str:
    """La misma URL, pero sin `request`: la usa el proceso que vacía la cola."""
    path = reverse("sessions-task-edit", args=[int(task.id)])
    query = "embedded=1&snapshot=1"
    team_id = getattr(getattr(getattr(task, "session", None), "team", None), "id", None)
    if team_id:
        query += f"&team={int(team_id)}"
    return f"{str(base_url).rstrip('/')}{path}?{query}"


# ---------------------------------------------------------------------------
# La COLA. Pedir una foto es escribir una fila, no lanzar un hilo.
#
# El proceso web no fotografía nada: sólo deja el encargo apuntado. Quien lo cumple es otro
# proceso (`manage.py fotos_pizarra`), que puede morirse a mitad sin perder el encargo. Ver el
# porqué en el docstring de `TaskBoardShot`.
# ---------------------------------------------------------------------------
def request_snapshot(task, user=None, *, force: bool = False):
    """Apunta que esta tarea necesita foto. Devuelve la fila, o None si no hace falta.

    Es idempotente: llamarla en cada visita a la ficha no acumula trabajo, sólo mantiene la fila
    al día. Si el dibujo ha cambiado desde el último encargo, los intentos vuelven a cero: una
    pizarra nueva merece sus reintentos aunque la anterior se rindiera.
    """
    from django.db import transaction

    from .models import TaskBoardShot

    if not getattr(settings, "TASK_BOARD_SNAPSHOT_ENABLED", True):
        return None
    try:
        task_id = int(getattr(task, "id", 0) or 0)
    except Exception:
        return None
    if not task_id:
        return None
    if not force and snapshot_is_current(task):
        return None
    sig = board_signature(task)
    if not sig:
        return None

    ahora = timezone.now()
    usuario = user if getattr(user, "is_authenticated", False) else None
    with transaction.atomic():
        shot, creada = TaskBoardShot.objects.select_for_update().get_or_create(
            task_id=task_id,
            defaults={
                "signature": sig,
                "state": TaskBoardShot.PENDIENTE,
                "requested_by": usuario,
                "next_try_at": ahora,
            },
        )
        if creada:
            return shot

        dibujo_nuevo = shot.signature != sig
        if dibujo_nuevo or force:
            shot.signature = sig
            shot.state = TaskBoardShot.PENDIENTE
            shot.attempts = 0
            shot.last_error = ""
            shot.next_try_at = ahora
            shot.leased_until = None
            shot.requested_at = ahora
        elif shot.state == TaskBoardShot.HECHA:
            # La firma es la misma pero la foto guardada ya no vale (p.ej. el editor la
            # sobrescribió con su captura de 720 px al guardar). Vuelve a la cola.
            shot.state = TaskBoardShot.PENDIENTE
            shot.next_try_at = ahora
        if usuario is not None:
            # Siempre la última persona que la pidió: si a quien la encargó le quitan el acceso,
            # el encargo no se queda muerto esperando una sesión que ya no se puede crear.
            shot.requested_by = usuario
        shot.save()
    return shot


def shot_for(task):
    from .models import TaskBoardShot

    try:
        return TaskBoardShot.objects.filter(task_id=int(task.id)).first()
    except Exception:
        return None


def shot_state_for(task) -> dict:
    """Lo que la ficha necesita contar: ¿viene la foto, o se rindió y por qué?"""
    from .models import TaskBoardShot

    if snapshot_is_current(task):
        return {"pendiente": False, "rendida": False, "motivo": "", "intentos": 0}
    shot = shot_for(task)
    if shot is None:
        return {"pendiente": False, "rendida": False, "motivo": "", "intentos": 0}
    rendida = shot.state == TaskBoardShot.RENDIDA
    return {
        "pendiente": not rendida,
        "rendida": rendida,
        "motivo": shot.last_error or "",
        "intentos": int(shot.attempts or 0),
    }


def _espera_tras_fallo(intentos: int) -> int:
    """Segundos hasta el siguiente intento: 1, 4, 9, 16, 25 minutos.

    Antes era un plano de 30 minutos guardado en `cache`, y hacía dos cosas mal: castigaba media
    hora un fallo que casi siempre era pasajero (el worker reiniciándose), y como la caché es por
    proceso, sólo frenaba a uno de los dos workers.
    """
    n = max(1, int(intentos or 1))
    return min(n * n, 25) * 60


def claim_pending(limit: int = 1, lease_seconds: int = 15 * 60) -> list:
    """Coge encargos de la cola y los alquila para que nadie más los toque.

    El alquiler CADUCA a propósito: si el proceso que fotografía se muere a mitad —que es
    exactamente lo que pasaba antes—, el encargo vuelve a la cola solo en cuanto pasa el plazo.
    """
    from django.db import transaction

    from .models import TaskBoardShot

    ahora = timezone.now()
    cogidos = []
    with transaction.atomic():
        libres = (
            TaskBoardShot.objects
            .select_for_update(skip_locked=True)
            .filter(state=TaskBoardShot.PENDIENTE)
            .filter(models.Q(next_try_at__isnull=True) | models.Q(next_try_at__lte=ahora))
            .filter(models.Q(leased_until__isnull=True) | models.Q(leased_until__lte=ahora))
            .order_by("next_try_at", "requested_at")[: max(1, int(limit))]
        )
        for shot in libres:
            shot.leased_until = ahora + timedelta(seconds=int(lease_seconds))
            shot.save(update_fields=["leased_until", "updated_at"])
            cogidos.append(shot)
    return cogidos


def mark_done(shot) -> None:
    from .models import TaskBoardShot

    shot.state = TaskBoardShot.HECHA
    shot.last_error = ""
    shot.leased_until = None
    shot.next_try_at = None
    shot.save(update_fields=["state", "last_error", "leased_until", "next_try_at", "updated_at"])


def mark_failed(shot, motivo: str) -> None:
    """Apunta el fallo EN LA BASE, que es donde se ve desde cualquier worker."""
    from .models import TaskBoardShot

    shot.attempts = int(shot.attempts or 0) + 1
    shot.last_error = str(motivo or "")[:400]
    shot.leased_until = None
    if shot.attempts >= TaskBoardShot.MAX_INTENTOS:
        # Rendirse no es callarse: el estado y el motivo quedan a la vista en la ficha.
        shot.state = TaskBoardShot.RENDIDA
        shot.next_try_at = None
    else:
        shot.next_try_at = timezone.now() + timedelta(seconds=_espera_tras_fallo(shot.attempts))
    shot.save(update_fields=["attempts", "last_error", "leased_until", "state", "next_try_at", "updated_at"])


def cookies_for_user(user, base_url: str) -> list:
    """Sesión recién hecha para ese usuario, sin pasar por un request.

    La foto abre el EDITOR REAL, que exige estar autenticado. El proceso que vacía la cola no
    tiene request del que copiar la cookie, así que se crea una sesión de la persona que pidió la
    foto: los permisos siguen siendo los suyos y no hace falta inventar una cuenta de servicio.
    """
    import importlib

    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY

    if user is None or not getattr(user, "pk", None):
        return []
    motor = importlib.import_module(settings.SESSION_ENGINE)
    sesion = motor.SessionStore()
    sesion[SESSION_KEY] = str(user.pk)
    sesion[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    sesion[HASH_SESSION_KEY] = user.get_session_auth_hash()
    sesion.create()
    clave = sesion.session_key
    if not clave:
        # `signed_cookies` no guarda nada en servidor y no da clave. En producción usamos el
        # motor de base de datos, pero si alguien lo cambia hay que enterarse, no fallar mudo.
        raise RuntimeError(
            f"SESSION_ENGINE={settings.SESSION_ENGINE} no genera clave de sesión: "
            "la foto no puede autenticarse"
        )
    return [{
        "name": getattr(settings, "SESSION_COOKIE_NAME", "sessionid"),
        "value": str(clave),
        "url": str(base_url),
    }]


def board_object_count(task) -> int:
    """Cuantos objetos tiene el dibujo. Sirve para dar mas tiempo a las pizarras cargadas."""
    from .task_library_services import extract_canvas_state_for_preview

    try:
        canvas_state, _w, _h = extract_canvas_state_for_preview(task)
    except Exception:
        return 0
    objects = canvas_state.get("objects") if isinstance(canvas_state, dict) else None
    return len(objects) if isinstance(objects, list) else 0


def _timeouts_for(object_count: int) -> tuple[int, int]:
    """(timeout_ms, settle_ms) segun el tamanio del dibujo.

    Con 60 s fijos las tareas importadas del PPT (400-1000 objetos, y la pagina del editor
    pesando megas) NO llegaban a `__WEBSTATS_SNAPSHOT_READY` y la ficha se quedaba con la
    miniatura vieja. Cada objeto es una imagen o un grupo de Fabric que hay que cargar y
    pintar, asi que el tiempo tiene que ir con el numero de objetos, no ser una constante.
    """
    count = max(0, int(object_count or 0))
    timeout_ms = min(SNAPSHOT_TIMEOUT_MAX_MS, SNAPSHOT_TIMEOUT_BASE_MS + count * SNAPSHOT_TIMEOUT_PER_OBJECT_MS)
    settle_ms = 1500 if count < 200 else 3000
    return timeout_ms, settle_ms


def cumplir_encargo(shot, base_url: str) -> tuple[bool, str]:
    """Hace la foto de un encargo ya alquilado. Devuelve (salió bien, explicación).

    No lanza: cualquier fallo vuelve como explicación para que quede escrito en la fila. El
    blindaje de siempre sigue en pie — si la foto sale como campo pelado, NO se pisa la imagen
    buena que la tarea ya tuviera.
    """
    from .models import SessionTask

    task = SessionTask.objects.filter(pk=int(shot.task_id)).first()
    if task is None:
        return False, "la tarea ya no existe"
    if snapshot_is_current(task):
        return True, "ya estaba al día"

    sig = board_signature(task)
    if not sig:
        return False, "la tarea no tiene dibujo que fotografiar"

    usuario = shot.requested_by
    if usuario is None:
        return False, "nadie con permiso la ha pedido: abre la ficha una vez y se reintenta"
    try:
        cookies = cookies_for_user(usuario, base_url)
    except Exception as exc:
        return False, f"no se pudo crear la sesión de {usuario}: {exc}"
    if not cookies:
        return False, f"no se pudo crear la sesión de {usuario}"

    # "No hay navegador" y "la pizarra no cargó a tiempo" son problemas DISTINTOS —uno se arregla
    # instalando algo y el otro esperando más— y el mensaje los daba juntos. Se comprueba antes,
    # que además es instantáneo, para que el motivo escrito en la fila sirva de algo.
    try:
        import playwright  # noqa: F401
    except Exception:
        return False, "Playwright no está instalado en este proceso: sin navegador no hay foto"

    url = editor_snapshot_url_for(task, base_url)
    objetos = board_object_count(task)
    try:
        png = _render(url, cookies, objetos)
    except _ColaLlena:
        # NO es un fallo de la foto: es que habia otras delante. Distinguirlo no es un detalle,
        # es la diferencia entre "esto esta roto" y "esto va en fila"; el diagnostico decia
        # "(sin motivo guardado)" y parecia una averia. Por eso NO cuenta como intento: se
        # devuelve a la cola tal cual, sin gastar uno de los cinco.
        shot.leased_until = None
        shot.save(update_fields=["leased_until", "updated_at"])
        return False, "__en_cola__"
    except Exception as exc:
        logger.exception("board snapshot: fallo en tarea %s", shot.task_id)
        return False, f"{type(exc).__name__}: {exc}"

    if not png:
        timeout_ms, _settle = _timeouts_for(objetos)
        return False, (
            f"la pizarra no llegó a estar lista en {timeout_ms // 1000}s ({objetos} objetos); "
            f"o el navegador no pudo abrir {url}"
        )
    if not _looks_like_a_real_board(png):
        return False, f"descartada: la foto sale como campo vacío · {_stats_text(png)}"

    jpeg = _to_jpeg(png)
    _store(int(task.id), jpeg, sig)
    task.refresh_from_db()
    if not snapshot_is_current(task):
        # `_store` descarta si el dibujo cambió mientras fotografiábamos. No es un fallo del
        # sistema: es que hay una versión más nueva, y su encargo ya está en la cola.
        return False, "el dibujo cambió mientras se hacía la foto; se repetirá con el nuevo"
    return True, f"ok · {len(jpeg)} bytes"


class _ColaLlena(Exception):
    """La foto no se intento: habia otras delante y se agoto la espera en la cola."""


def _render(url: str, cookies: list, object_count: int = 0) -> bytes | None:
    if not _render_gate.acquire(timeout=RENDER_GATE_TIMEOUT_SECONDS):
        logger.warning("board snapshot: cola llena, se salta esta foto")
        # Se pierde el motivo mas util que hay: no es que la foto fallara, es que ni se intento
        # porque delante habia otras. Sin esto, el diagnostico dice "(sin motivo guardado)" y
        # parece una averia cuando es una cola.
        raise _ColaLlena()
    try:
        return _render_locked(url, cookies, object_count)
    finally:
        _render_gate.release()


def _render_locked(url: str, cookies: list, object_count: int = 0) -> bytes | None:
    from .preview_render import render_url_selector_png

    timeout_ms, settle_ms = _timeouts_for(object_count)
    return render_url_selector_png(
        url=url,
        selector=SNAPSHOT_SELECTOR,
        cookies=cookies,
        viewport_width=SNAPSHOT_VIEWPORT_WIDTH,
        viewport_height=SNAPSHOT_VIEWPORT_HEIGHT,
        device_scale_factor=SNAPSHOT_DEVICE_SCALE,
        wait_for_js=SNAPSHOT_READY_JS,
        timeout_ms=timeout_ms,
        settle_ms=settle_ms,
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
    """Ultima comprobacion: que la imagen sea una imagen y tenga tamanio de pizarra.

    Aqui habia una heuristica de color (verde/blanco) heredada de las miniaturas, y era la que
    estaba TIRANDO FOTOS BUENAS. Mide sobre una reduccion a 128 px: a esa escala una linea de
    campo de 4 px se mezcla con el cesped y deja de contar como blanco, asi que una foto
    impecable de campo entero salia como "verde=0.97 blanco=0.00" y se descartaba. Solo se
    salvaban las que tenian chapas amarillas o dorsales blancos, de ahi que unas tareas si y
    otras no, sin patron.

    El guardia de verdad esta en el navegador: la foto no se dispara hasta que el campo esta
    pintado (imagenes del cesped incluidas) y la capa de Fabric tiene pixeles.
    """
    from .task_library_services import analyze_preview_image_bytes

    if not png_bytes or len(png_bytes) < 2048:
        return False
    stats = analyze_preview_image_bytes(png_bytes)
    if not stats:
        return True  # sin Pillow no podemos juzgar: no bloqueamos
    try:
        width = int(stats.get("width") or 0)
        height = int(stats.get("height") or 0)
    except Exception:
        return True
    return min(width, height) >= 200


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
    campos = ["task_preview_image", "tactical_layout"]

    # Y LA PORTADA TAMBIEN. La peticion era que la captura de la pizarra fuera "a la portada y a
    # la ficha", y la portada NO se estaba actualizando NUNCA: en todo views.py `cover_data_b64`
    # solo se lee. Como la tarjeta de biblioteca pinta la portada ANTES que la foto de la
    # pizarra, en las 512 tareas que tienen portada propia el dibujo nuevo no se veia jamas, por
    # bien que saliera la foto. Se arreglaba la mitad invisible del problema.
    #
    # Pisarla es seguro y es lo que se pidio: las portadas de produccion son capturas de pizarra
    # viejas (736x476), no las portadas fotorrealistas; se comprobo mirandolas antes de tocar
    # nada. Aqui la sustituimos por la de ahora, reducida para que la tarjeta siga siendo ligera.
    portada = _portada_desde_foto(image_bytes)
    if portada:
        task.cover_data_b64 = portada
        campos.append("cover_data_b64")
    task.save(update_fields=campos)


# Ancho de la portada de la tarjeta. Las que hay en produccion rondan los 736-960 px; con mas
# solo se engorda el listado, que ya arrastro un problema de peso por meter imagenes grandes.
COVER_MAX_WIDTH = 960
COVER_QUALITY = 82


def _portada_desde_foto(image_bytes: bytes) -> str:
    """La misma foto, reducida, como data URI para `cover_data_b64`."""
    if Image is None:
        return ""
    try:
        with Image.open(io.BytesIO(image_bytes)) as foto:
            foto = foto.convert("RGB")
            if foto.width > COVER_MAX_WIDTH:
                alto = max(1, round(foto.height * COVER_MAX_WIDTH / foto.width))
                foto = foto.resize((COVER_MAX_WIDTH, alto), Image.LANCZOS)
            buf = io.BytesIO()
            foto.save(buf, format="JPEG", quality=COVER_QUALITY, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        logger.exception("board snapshot: no se pudo hacer la portada")
        return ""


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
def board_snapshot_upload_view(request, task_id):
    """Guarda una foto de la pizarra hecha FUERA del servidor.

    Existe porque hacer las fotos aqui no siempre es viable: en Render corremos con un
    unico worker y Chromium compite con la propia app; con una biblioteca entera por
    fotografiar la instancia se reinicia (502) y no termina nunca. Fotografiando desde
    otra maquina, el servidor solo tiene que servir la pagina del editor.

    Sube exactamente lo mismo que produce el hilo interno (`_store`): la imagen como
    `task-<id>-board-hd.jpg` y la firma del dibujo, para que `snapshot_is_current` la de
    por buena y no se vuelva a intentar.
    """
    from django.http import JsonResponse

    from .models import SessionTask
    from .permissions import can_access_sessions_workspace

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    task = SessionTask.objects.filter(pk=int(task_id)).first()
    if not task:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    imagen = request.FILES.get("image")
    if not imagen:
        return JsonResponse({"ok": False, "error": "sin imagen"}, status=400)
    raw = imagen.read()
    if not raw or len(raw) > 12 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "tamanio de imagen no valido"}, status=400)
    if not _looks_like_a_real_board(raw):
        return JsonResponse({"ok": False, "error": "la imagen no parece una pizarra"}, status=400)

    sig = board_signature(task)
    if not sig:
        return JsonResponse({"ok": False, "error": "la tarea no tiene dibujo"}, status=400)
    # La firma que manda es la del dibujo ACTUAL: si la pizarra ha cambiado desde que se
    # hizo la foto fuera, `_store` la descarta sola (misma proteccion que el hilo interno).
    enviada = str(request.POST.get("signature") or "").strip()
    if enviada and enviada != sig:
        return JsonResponse({"ok": False, "error": "la pizarra cambio despues de la foto"}, status=409)

    _store(int(task.id), _to_jpeg(raw) if raw[:2] != b"\xff\xd8" else raw, sig)
    task.refresh_from_db()
    return JsonResponse({"ok": True, "task": int(task.id), "al_dia": snapshot_is_current(task)})


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

        png = _render(editor_snapshot_url(request, task), session_cookies_for(request), board_object_count(task))
        if not png:
            return JsonResponse({"ok": False, "error": "sin foto (Playwright o pizarra no lista)"}, status=503)
        resp = HttpResponse(png, content_type="image/png")
        resp["X-Board-Stats"] = _stats_text(png)
        resp["Cache-Control"] = "no-store"
        return resp

    if str(request.GET.get("probe") or "").strip() in {"1", "true", "yes"}:
        return JsonResponse(_probe(request, task))

    force = str(request.GET.get("force") or "").strip() in {"1", "true", "yes"}
    # Consultar el estado NO fotografía nada: sólo (re)apunta el encargo. Quien lo cumple es
    # `manage.py fotos_pizarra`, fuera de este proceso.
    shot = request_snapshot(task, request.user, force=force) if force else shot_for(task)

    field = getattr(task, "task_preview_image", None)
    return JsonResponse({
        "ok": True,
        "task": int(task.id),
        "is_current": snapshot_is_current(task),
        "signature": board_signature(task),
        "stored_signature": stored_signature(task),
        "image": str(getattr(field, "name", "") or ""),
        "estado": getattr(shot, "state", "") if shot else "sin encargo",
        "intentos": int(getattr(shot, "attempts", 0) or 0) if shot else 0,
        "proximo_intento": (
            shot.next_try_at.isoformat() if shot and shot.next_try_at else ""
        ),
        "alquilado_hasta": (
            shot.leased_until.isoformat() if shot and shot.leased_until else ""
        ),
        "last_note": getattr(shot, "last_error", "") if shot else "",
        "url": editor_snapshot_url(request, task),
    })


def board_snapshot_batch_view(request):
    """Mete en la cola las tareas sin foto al día: `?limit=` (por defecto 12, maximo 200).

    Ya no levanta ningun Chromium aqui: solo apunta encargos. El servicio de fotos los va
    vaciando de uno en uno, asi que pedir 200 no tumba nada, solo tarda mas en terminar.
    """
    from django.http import JsonResponse

    from .models import SessionTask
    from .permissions import can_access_sessions_workspace

    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        limit = int(request.GET.get("limit") or 12)
    except Exception:
        limit = 12
    limit = max(1, min(limit, 200))

    qs = SessionTask.objects.order_by("-id")
    try:
        team_id = int(request.GET.get("team") or 0)
    except Exception:
        team_id = 0
    if team_id:
        qs = qs.filter(session__microcycle__team_id=team_id)

    encoladas = []
    for task in qs.iterator():
        if snapshot_is_current(task):
            continue
        if request_snapshot(task, request.user) is not None:
            encoladas.append(int(task.id))
        if len(encoladas) >= limit:
            break

    return JsonResponse({
        "ok": True,
        "encoladas": len(encoladas),
        "ids": encoladas,
        "nota": "Apuntadas en la cola. El servicio de fotos las va haciendo de una en una.",
    })

_PROBE_JS = """() => {
  const out = {};
  try { out.tpad_listo = window.__WEBSTATS_TPAD_READY === true; } catch (e) { out.tpad_listo = 'err'; }
  try { out.foto_lista = window.__WEBSTATS_SNAPSHOT_READY === true; } catch (e) { out.foto_lista = 'err'; }
  try { out.modo_foto = document.body ? document.body.classList.contains('edc-snapshot') : false; } catch (e) {}
  try {
    const err = window.__WEBSTATS_LAST_TPAD_ERROR;
    out.error_pizarra = err ? String(err.message || err).slice(0, 220) : '';
  } catch (e) {}
  try {
    const stage = document.getElementById('task-pitch-stage');
    out.escenario = stage ? Math.round(stage.getBoundingClientRect().width) + 'x' + Math.round(stage.getBoundingClientRect().height) : 'no hay';
  } catch (e) {}
  try {
    const c = document.querySelector('#task-pitch-stage canvas.lower-canvas') || document.getElementById('create-task-canvas');
    out.lienzo = c ? (c.width + 'x' + c.height) : 'no hay';
    if (c && c.width) {
      const s = document.createElement('canvas');
      s.width = 160; s.height = Math.max(1, Math.round(160 * c.height / c.width));
      const sc = s.getContext('2d', { willReadFrequently: true });
      sc.clearRect(0, 0, s.width, s.height);
      sc.drawImage(c, 0, 0, s.width, s.height);
      const d = sc.getImageData(0, 0, s.width, s.height).data;
      let n = 0;
      for (let i = 3; i < d.length; i += 4) { if (d[i] > 16) n++; }
      out.pixeles_pintados = n;
    }
  } catch (e) { out.lienzo_error = String(e).slice(0, 160); }
  return out;
}"""


def _probe(request, task) -> dict:
    from .preview_render import probe_url_state

    url = editor_snapshot_url(request, task)
    state = probe_url_state(
        url=url,
        cookies=session_cookies_for(request),
        script=_PROBE_JS,
        viewport_width=SNAPSHOT_VIEWPORT_WIDTH,
        viewport_height=SNAPSHOT_VIEWPORT_HEIGHT,
        wait_ms=25000,
    )
    return {"ok": True, "task": int(task.id), "url": url, "estado": state}
