"""Acciones del asistente: entender la orden, ENSEÑAR lo que va a hacer, y hacerlo al confirmar.

La regla de la casa, y no es un formalismo: **nunca se escribe sin confirmación explícita**.
Hoy mismo se descubrió que el guardián reparaba datos del club porque alguien le hacía una
pregunta; escribir en la ficha de un jugador porque una frase encajó con unas palabras es el
mismo error con otro nombre. Piensa en dos jugadores que se llamen Nico, o en un "ausente"
escrito con prisa desde la banda.

Por eso el ciclo es de dos pasos:

  1. Le pides algo  -> el asistente responde QUÉ va a hacer, con nombre, dorsal y fecha, y
                       espera. No ha tocado nada.
  2. Confirmas      -> lo hace, por el mismo camino que la pantalla, y queda registrado quién
                       lo pidió (`marked_by`).

De momento SOLO asistencia, y a propósito: es lo que tocas cada semana y se deshace en un
clic. Lesiones y evaluaciones son harina de otro costal —ahí una equivocación cuesta— y entran
cuando esto lleve tiempo funcionando.
"""
from __future__ import annotations

import logging
import time
import unicodedata

logger = logging.getLogger(__name__)

CLAVE_SESION = "asistente_pendiente"
# Una orden a medias caduca: si vuelves media hora después y dices "sí", no puedes acordarte
# de qué estabas confirmando. Y el asistente tampoco debería.
VALIDEZ_SEGUNDOS = 300

SI = {"si", "sí", "confirmo", "confirmado", "adelante", "hazlo", "dale", "ok", "okey", "vale",
      "correcto", "eso es", "exacto", "venga"}
NO = {"no", "cancela", "cancelar", "dejalo", "déjalo", "para", "olvidalo", "olvídalo", "anula"}

# Cómo se dice cada estado y cómo lo llama él.
ESTADOS = (
    # En pasado tambien: la asistencia se apunta DESPUES del entreno, y ahi nadie dice
    # "no viene", dice "no vino" o "faltó".
    ("absent", "ausente", ("ausente", "ausencia", "no viene", "no vino", "no ha venido",
                           "no va a venir", "no asiste", "no asistio", "no asistió",
                           "falta", "falto", "faltó")),
    ("present", "presente", ("presente", "si viene", "asiste", "asistio", "asistió",
                             "vino", "ha venido", "viene")),
    ("late", "llega tarde", ("tarde", "retraso", "llega tarde")),
    ("injured", "lesionado", ("lesionado", "lesionada", "lesion")),
    ("excused", "justificado", ("justificado", "justificada", "con permiso", "excusado")),
)


def _sin_tildes(texto: str) -> str:
    crudo = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", crudo) if not unicodedata.combining(c))


def es_confirmacion(texto: str) -> str:
    """Devuelve 'si', 'no' o '' según lo que haya escrito."""
    q = _sin_tildes(texto).strip(" .!¡?¿")
    if q in {_sin_tildes(x) for x in SI}:
        return "si"
    if q in {_sin_tildes(x) for x in NO}:
        return "no"
    return ""


def estado_pedido(texto: str):
    """(clave, etiqueta) del estado de asistencia que se pide, o None."""
    q = _sin_tildes(texto)
    mejor = None
    for clave, etiqueta, palabras in ESTADOS:
        for p in palabras:
            if p in q and (mejor is None or len(p) > mejor[0]):
                mejor = (len(p), clave, etiqueta)
    if mejor is None:
        return None
    return mejor[1], mejor[2]


def _nombre_visible(jugador):
    return str(getattr(jugador, "name", "") or getattr(jugador, "full_name", "") or "").strip()


def describir(jugador, estado_etiqueta, sesion):
    """El texto que se le enseña ANTES de tocar nada. Concreto a propósito: nombre, dorsal y
    fecha son lo que le permite decir 'ese no'."""
    quien = _nombre_visible(jugador)
    dorsal = str(getattr(jugador, "number", "") or "").strip()
    if dorsal:
        quien += f" (dorsal {dorsal})"
    fecha = ""
    try:
        fecha = sesion.session_date.strftime("%d/%m/%Y") if sesion.session_date else ""
    except Exception:
        fecha = ""
    foco = str(getattr(sesion, "focus", "") or "").strip()
    cuando = f"la sesión del {fecha}" if fecha else "la sesión"
    if foco:
        cuando += f" ({foco[:40]})"
    return f"Voy a marcar a {quien} como {estado_etiqueta} en {cuando}. ¿Confirmo?"


def guardar_pendiente(request, *, player_id, session_id, estado, resumen):
    request.session[CLAVE_SESION] = {
        "player_id": int(player_id),
        "session_id": int(session_id),
        "estado": str(estado),
        "resumen": str(resumen)[:300],
        "ts": int(time.time()),
    }
    request.session.modified = True


def leer_pendiente(request):
    dato = request.session.get(CLAVE_SESION)
    if not isinstance(dato, dict):
        return None
    if int(time.time()) - int(dato.get("ts") or 0) > VALIDEZ_SEGUNDOS:
        olvidar(request)
        return None
    return dato


def olvidar(request):
    try:
        if CLAVE_SESION in request.session:
            del request.session[CLAVE_SESION]
            request.session.modified = True
    except Exception:
        pass


def ejecutar(request, pendiente):
    """Escribe la asistencia. Mismo criterio que la pantalla de la sesión.

    OJO con la regla que no es obvia: PRESENTE se guarda BORRANDO la marca. La ausencia de
    fila significa "vino". Si aquí se creara una fila con status='present', la pantalla y el
    asistente contarían cosas distintas.
    """
    from football.models import Player, TrainingSession, TrainingSessionAttendance

    try:
        jugador = Player.objects.filter(id=int(pendiente["player_id"])).first()
        sesion = TrainingSession.objects.filter(id=int(pendiente["session_id"])).first()
        if jugador is None or sesion is None:
            return False, "Ya no encuentro a ese jugador o esa sesión. No he cambiado nada."

        estado = str(pendiente.get("estado") or "")
        validos = {v for v, _ in TrainingSessionAttendance.STATUS_CHOICES}
        if estado not in validos:
            return False, "No reconozco ese estado. No he cambiado nada."

        if estado == TrainingSessionAttendance.STATUS_PRESENT:
            TrainingSessionAttendance.objects.filter(session=sesion, player=jugador).delete()
        else:
            TrainingSessionAttendance.objects.update_or_create(
                session=sesion,
                player=jugador,
                defaults={
                    "status": estado,
                    "marked_by": request.user if getattr(request.user, "is_authenticated", False) else None,
                },
            )
        etiqueta = dict(TrainingSessionAttendance.STATUS_CHOICES).get(estado, estado)
        quien = _nombre_visible(jugador)
        logger.info(
            "asistente: %s marcado como %s en la sesion %s por %s",
            quien, etiqueta, sesion.id, getattr(request.user, "username", "?"),
        )
        fecha = ""
        try:
            fecha = sesion.session_date.strftime("%d/%m") if sesion.session_date else ""
        except Exception:
            fecha = ""
        return True, (
            f"Hecho: {quien} queda como {etiqueta}"
            + (f" en la sesión del {fecha}" if fecha else "")
            + f".\n\nRevisar: /coach/sesiones/sesion/{int(sesion.id)}/"
        )
    except Exception:
        logger.debug("el asistente no pudo escribir la asistencia", exc_info=True)
        return False, "No he podido guardarlo. Mejor hazlo en la pantalla de la sesión."
