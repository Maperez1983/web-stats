"""Preguntas sobre entrenamientos que el asistente no sabía contestar.

Salieron probándolo: «quién no vino al último entreno», «cuántas sesiones tengo esta semana»,
«qué tareas hice el martes». Las tres caían en el guardián, que tardaba entre 7 y 10 segundos
para contestar con un parte del servidor.

Son consultas: no escriben nada y no necesitan confirmación. Van contra la base de datos y
tardan milisegundos.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import timedelta

logger = logging.getLogger(__name__)

DIAS = (
    ("lunes", 0), ("martes", 1), ("miercoles", 2), ("miércoles", 2),
    ("jueves", 3), ("viernes", 4), ("sabado", 5), ("sábado", 5), ("domingo", 6),
)


def _sin_tildes(texto: str) -> str:
    crudo = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", crudo) if not unicodedata.combining(c))


def _sesiones_de_verdad(qs):
    """Sin las de biblioteca: son plantillas, no entrenamientos."""
    from football.views import _is_library_session

    return [s for s in qs if not _is_library_session(s)]


def dia_pedido(frase):
    """Qué día de la semana nombra la frase (0=lunes) o None."""
    q = _sin_tildes(frase)
    for nombre, indice in DIAS:
        if re.search(r"\b" + _sin_tildes(nombre) + r"\b", q):
            return indice
    return None


def sesion_referida(frase, equipo):
    """La sesión de la que habla: «del martes», «la última», «la próxima»."""
    from django.utils import timezone

    from football.models import TrainingSession

    hoy = timezone.localdate()
    q = _sin_tildes(frase)
    base = TrainingSession.objects.select_related("microcycle").filter(microcycle__team=equipo)

    dia = dia_pedido(frase)
    if dia is not None:
        # El más cercano en el tiempo, mirando 10 días atrás y 10 adelante: «el martes» puede
        # ser el que viene o el que acaba de pasar, y lo natural es el que está más cerca de hoy.
        ventana = _sesiones_de_verdad(
            base.filter(session_date__gte=hoy - timedelta(days=10),
                        session_date__lte=hoy + timedelta(days=10))
            .order_by("session_date")
        )
        delDia = [s for s in ventana if s.session_date and s.session_date.weekday() == dia]
        if delDia:
            return min(delDia, key=lambda s: abs((s.session_date - hoy).days))
        return None

    if any(p in q for p in ("ultimo", "ultima", "pasado", "pasada", "anterior", "ayer")):
        celebradas = _sesiones_de_verdad(
            base.filter(session_date__lte=hoy).order_by("-session_date", "-id")[:10]
        )
        return celebradas[0] if celebradas else None

    proximas = _sesiones_de_verdad(
        base.filter(session_date__gte=hoy).order_by("session_date", "start_time", "id")[:10]
    )
    return proximas[0] if proximas else None


# --- Las tres preguntas ----------------------------------------------------------------------

def es_pregunta_asistencia(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("quien", "quienes", "cuantos"))
            and any(p in q for p in ("vino", "vinieron", "falto", "faltaron", "falta",
                                     "asistio", "asistieron", "ausente", "ausentes")))


def responder_asistencia(frase, equipo):
    from football.models import TrainingSessionAttendance

    sesion = sesion_referida(frase, equipo)
    if sesion is None:
        return {"message": "No encuentro esa sesión.", "highlights": []}
    marcas = list(
        TrainingSessionAttendance.objects.select_related("player")
        .filter(session=sesion)
        .order_by("status", "player__name")
    )
    fecha = sesion.session_date.strftime("%d/%m") if sesion.session_date else ""
    if not marcas:
        # Sin marcas = vinieron todos: la ausencia de fila significa "presente".
        return {"message": f"En la sesión del {fecha} no hay nadie marcado: vinieron todos.",
                "highlights": ["Todos"]}
    etiquetas = dict(TrainingSessionAttendance.STATUS_CHOICES)
    porEstado = {}
    for m in marcas:
        porEstado.setdefault(m.status, []).append(str(getattr(m.player, "name", "") or ""))
    lineas = [f"· {etiquetas.get(k, k)}: {', '.join(v)}" for k, v in porEstado.items()]
    return {
        "message": f"Sesión del {fecha}:\n" + "\n".join(lineas)
                   + f"\n\nVer: /coach/sesiones/sesion/{int(sesion.id)}/",
        "highlights": [etiquetas.get(k, k) for k in porEstado][:4],
    }


def es_pregunta_tareas_de_sesion(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("que tareas", "que ejercicios", "que hice", "que hicimos",
                                 "que entrene", "que entrenamos", "que trabaje"))
            and not any(p in q for p in ("biblioteca", "sugiere", "recomienda")))


def responder_tareas_de_sesion(frase, equipo):
    from football.models import SessionTask

    sesion = sesion_referida(frase, equipo)
    if sesion is None:
        return {"message": "No encuentro esa sesión.", "highlights": []}
    tareas = list(
        SessionTask.objects.defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        .filter(session=sesion, deleted_at__isnull=True)
        .order_by("order", "id")[:20]
    )
    fecha = sesion.session_date.strftime("%d/%m") if sesion.session_date else ""
    if not tareas:
        return {"message": f"La sesión del {fecha} no tiene tareas todavía.", "highlights": []}
    bloques = dict(SessionTask.BLOCK_CHOICES)
    lineas = [
        f"· {str(t.title or '(sin título)')[:44]}"
        f" — {bloques.get(t.block, '')}, {int(t.duration_minutes or 0)} min"
        for t in tareas
    ]
    return {
        "message": f"Sesión del {fecha} ({len(tareas)} tareas):\n" + "\n".join(lineas)
                   + f"\n\nVer: /coach/sesiones/sesion/{int(sesion.id)}/",
        "highlights": [str(t.title or "")[:30] for t in tareas[:4]],
    }


def es_pregunta_cuantas_sesiones(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("cuantas", "cuantos", "que sesiones", "cuando entreno",
                                 "cuando entrenamos"))
            and any(p in q for p in ("sesion", "sesiones", "entreno", "entrenos",
                                     "entrenamiento", "entrenamientos")))


def responder_cuantas_sesiones(frase, equipo):
    from django.utils import timezone

    from football.models import TrainingSession

    hoy = timezone.localdate()
    q = _sin_tildes(frase)
    # «esta semana» = de lunes a domingo, no «los próximos siete días»: cuando alguien pregunta
    # el jueves «cuántas tengo esta semana» no cuenta las del martes que viene.
    if "semana que viene" in q or "proxima semana" in q:
        ini = hoy - timedelta(days=hoy.weekday()) + timedelta(days=7)
    else:
        ini = hoy - timedelta(days=hoy.weekday())
    fin = ini + timedelta(days=6)
    sesiones = _sesiones_de_verdad(
        TrainingSession.objects.select_related("microcycle")
        .filter(microcycle__team=equipo, session_date__gte=ini, session_date__lte=fin)
        .order_by("session_date", "start_time")
    )
    cuando = "la semana que viene" if ini > hoy else "esta semana"
    if not sesiones:
        return {"message": f"No tienes sesiones {cuando}.", "highlights": []}
    lineas = []
    for s in sesiones:
        hora = s.start_time.strftime("%H:%M") if getattr(s, "start_time", None) else ""
        foco = str(getattr(s, "focus", "") or "").strip()[:34]
        lineas.append(f"· {s.session_date.strftime('%a %d/%m')}"
                      + (f" {hora}" if hora else "") + (f" — {foco}" if foco else ""))
    return {
        "message": f"Tienes {len(sesiones)} sesión{'es' if len(sesiones) != 1 else ''} {cuando}:\n"
                   + "\n".join(lineas) + "\n\nVer: /coach/sesiones/",
        "highlights": [f"{len(sesiones)} sesiones"],
    }


CONSULTAS = (
    (es_pregunta_asistencia, responder_asistencia),
    (es_pregunta_tareas_de_sesion, responder_tareas_de_sesion),
    (es_pregunta_cuantas_sesiones, responder_cuantas_sesiones),
)


def responder(frase, equipo):
    """La primera consulta que reconozca la frase, o None."""
    if not equipo:
        return None
    for reconoce, contesta in CONSULTAS:
        try:
            if reconoce(frase):
                return contesta(frase, equipo)
        except Exception:
            logger.debug("una consulta del asistente fallo", exc_info=True)
    return None
