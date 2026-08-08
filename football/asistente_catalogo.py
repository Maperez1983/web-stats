"""Catálogo de acciones del asistente. Añadir una nueva son diez líneas, no un módulo.

Por qué un catálogo y no una función por acción: la lista de cosas que el asistente podría
hacer son unas cuarenta, y escritas a mano cada una acaba con su propio criterio de qué
confirmar, qué texto enseñar y qué comprobar. En un mes tienes cuarenta formas distintas de
equivocarse.

Aquí todas pasan por el mismo camino:

  1. `detectar(frase)` -> ¿alguna acción reconoce esto?
  2. `preparar(...)`    -> resuelve los datos (jugador, tarea, sesión...) y devuelve el TEXTO
                           que se le enseña al usuario. No escribe nada.
  3. el usuario dice sí
  4. `ejecutar(...)`    -> escribe, por el mismo camino que la pantalla.

Y todas heredan las mismas reglas, que son las que costaron sangre hoy:
  · nada se escribe sin confirmación explícita;
  · si algo es ambiguo se PREGUNTA, no se elige;
  · la confirmación enseña datos concretos (nombre, dorsal, fecha) para poder decir «ese no»;
  · comparar nombres contra texto libre exige `\\b` (hay un jugador que se llama Reno y
    encajaba dentro de «entreno»).
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


def sin_tildes(texto: str) -> str:
    crudo = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", crudo) if not unicodedata.combining(c))


def dice(frase: str, *palabras) -> bool:
    """¿La frase contiene alguna de estas palabras, como palabra suelta?"""
    q = sin_tildes(frase)
    return any(re.search(r"(?:^|\s)" + re.escape(sin_tildes(p)) + r"(?:\s|$)", q) for p in palabras)


def contiene(frase: str, *palabras) -> bool:
    """Como `dice`, pero admite trozos dentro de una palabra (para 'lesion' en 'lesionado')."""
    q = sin_tildes(frase)
    return any(sin_tildes(p) in q for p in palabras)


# --- Acciones -------------------------------------------------------------------------------
# Cada una: clave, cómo se reconoce, cómo se prepara y cómo se ejecuta.
# `preparar` devuelve (texto_a_confirmar, datos) o (texto_de_error, None) si no puede.

def _bloques():
    from football.models import SessionTask

    return dict(SessionTask.BLOCK_CHOICES)


def _bloque_pedido(frase):
    """Qué bloque de la sesión nombra la frase."""
    from football.models import SessionTask

    sinonimos = (
        (SessionTask.BLOCK_ACTIVATION, ("activacion", "calentamiento", "activar")),
        (SessionTask.BLOCK_PHYSICAL_PREP, ("preparacion fisica", "fisico", "fisica")),
        (SessionTask.BLOCK_CONDITIONING, ("condicionante",)),
        (SessionTask.BLOCK_MAIN_1, ("principal 1", "principal uno", "primera principal")),
        (SessionTask.BLOCK_MAIN_2, ("principal 2", "principal dos", "segunda principal")),
        (SessionTask.BLOCK_SET_PIECES, ("abp", "estrategia", "balon parado")),
        (SessionTask.BLOCK_RECOVERY, ("vuelta a la calma", "vuelta calma", "vuelta")),
        (SessionTask.BLOCK_VIDEO, ("video", "vídeo")),
    )
    q = sin_tildes(frase)
    mejor = None
    for clave, palabras in sinonimos:
        for p in palabras:
            if sin_tildes(p) in q and (mejor is None or len(p) > mejor[0]):
                mejor = (len(p), clave)
    return mejor[1] if mejor else ""


def _tarea_nombrada(frase, equipo):
    """La tarea a la que se refiere, buscando su título dentro de la frase.

    Devuelve (tarea, candidatas). Si hay varias, NO elige: quien llama pregunta.
    """
    from django.db.models import Q

    from football.models import SessionTask

    q = sin_tildes(frase)
    # Solo entre las suyas, y sin el lienzo: aquí solo hace falta el título.
    candidatas = []
    for t in (
        SessionTask.objects.select_related("session__microcycle")
        .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        .filter(session__microcycle__team=equipo, deleted_at__isnull=True)
        .order_by("-id")[:400]
    ):
        titulo = sin_tildes(str(getattr(t, "title", "") or "").strip())
        if len(titulo) >= 4 and titulo in q:
            candidatas.append(t)
    if len(candidatas) == 1:
        return candidatas[0], candidatas
    return None, candidatas


# ---- mover una tarea de bloque ---------------------------------------------------------------

def _mover_bloque_reconoce(frase):
    # NO se exige la palabra "tarea": nadie dice "mueve la tarea Rondo 6 vs 3", dice "mueve
    # Rondo 6 vs 3 a principal 2". Con el verbo y el bloque nombrado ya es inequivoco.
    return (dice(frase, "mueve", "mover", "pasa", "pasar", "cambia", "cambiar")
            and bool(_bloque_pedido(frase)))


def _mover_bloque_prepara(frase, ctx):
    tarea, candidatas = _tarea_nombrada(frase, ctx["equipo"])
    if tarea is None:
        if len(candidatas) > 1:
            nombres = ", ".join(str(t.title or "")[:30] for t in candidatas[:5])
            return f"¿Cuál de estas? {nombres}. Dímelo con el título completo.", None
        return ("No sé qué tarea es. Dime su título tal cual aparece, por ejemplo: "
                "«mueve Rondo 6 vs 3 a principal 2».", None)
    bloque = _bloque_pedido(frase)
    etiqueta = _bloques().get(bloque, bloque)
    actual = _bloques().get(getattr(tarea, "block", ""), "sin bloque")
    if getattr(tarea, "block", "") == bloque:
        return f"«{tarea.title}» ya está en {etiqueta}. No hay nada que cambiar.", None
    return (
        f"Voy a mover «{tarea.title}» de {actual} a {etiqueta}. ¿Confirmo?",
        {"tarea_id": int(tarea.id), "bloque": bloque},
    )


def _mover_bloque_ejecuta(datos, ctx):
    from football.models import SessionTask

    t = SessionTask.objects.filter(id=int(datos["tarea_id"])).first()
    if t is None:
        return False, "Esa tarea ya no está. No he cambiado nada."
    t.block = str(datos["bloque"])
    t.save(update_fields=["block"])
    return True, (f"Hecho: «{t.title}» queda en {_bloques().get(t.block, t.block)}."
                  f"\n\nRevisar: /coach/sesiones/tarea/{int(t.id)}/")


# ---- papelera: borrar y restaurar una tarea ---------------------------------------------------

def _borrar_reconoce(frase):
    # Aqui SI se exige la palabra "tarea", y es una asimetria buscada: mover algo de bloque se
    # deshace en un clic, y "borra" a secas es demasiado ambiguo para una accion destructiva.
    return (dice(frase, "borra", "borrar", "elimina", "eliminar", "quita", "quitar", "tira")
            and contiene(frase, "tarea", "ejercicio"))


def _borrar_prepara(frase, ctx):
    tarea, candidatas = _tarea_nombrada(frase, ctx["equipo"])
    if tarea is None:
        if len(candidatas) > 1:
            nombres = ", ".join(str(t.title or "")[:30] for t in candidatas[:5])
            return f"¿Cuál de estas? {nombres}.", None
        return "No sé qué tarea es. Dime su título tal cual.", None
    return (
        f"Voy a mandar «{tarea.title}» a la papelera. Se puede recuperar. ¿Confirmo?",
        {"tarea_id": int(tarea.id)},
    )


def _borrar_ejecuta(datos, ctx):
    from django.utils import timezone

    from football.models import SessionTask

    t = SessionTask.objects.filter(id=int(datos["tarea_id"]), deleted_at__isnull=True).first()
    if t is None:
        return False, "Esa tarea ya no está o ya estaba en la papelera."
    # A la PAPELERA, no borrado de verdad: `deleted_at`, igual que la pantalla. Un asistente
    # no puede destruir nada de forma irreversible por una frase.
    t.deleted_at = timezone.now()
    t.save(update_fields=["deleted_at"])
    return True, f"«{t.title}» está en la papelera. Dime «restaura {t.title}» y la saco."


def _restaurar_reconoce(frase):
    return (dice(frase, "restaura", "restaurar", "recupera", "recuperar", "devuelve")
            and contiene(frase, "tarea", "ejercicio"))


def _restaurar_prepara(frase, ctx):
    from football.models import SessionTask

    q = sin_tildes(frase)
    candidatas = [
        t for t in SessionTask.objects
        .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        .filter(session__microcycle__team=ctx["equipo"], deleted_at__isnull=False)
        .order_by("-deleted_at")[:200]
        if len(sin_tildes(str(t.title or ""))) >= 4 and sin_tildes(str(t.title or "")) in q
    ]
    if len(candidatas) != 1:
        if len(candidatas) > 1:
            return "¿Cuál? " + ", ".join(str(t.title or "")[:30] for t in candidatas[:5]), None
        return "No encuentro esa tarea en la papelera.", None
    t = candidatas[0]
    return f"Voy a sacar «{t.title}» de la papelera. ¿Confirmo?", {"tarea_id": int(t.id)}


def _restaurar_ejecuta(datos, ctx):
    from football.models import SessionTask

    t = SessionTask.objects.filter(id=int(datos["tarea_id"])).first()
    if t is None:
        return False, "Ya no encuentro esa tarea."
    t.deleted_at = None
    t.save(update_fields=["deleted_at"])
    return True, f"«{t.title}» vuelve a estar disponible.\n\nVer: /coach/sesiones/tarea/{int(t.id)}/"


# ---- seguimiento de un jugador ---------------------------------------------------------------

def _seguir_reconoce(frase):
    return (contiene(frase, "seguimiento", "seguir", "sigue", "fichar", "ojear")
            and not contiene(frase, "dejar de seguir", "quitar del seguimiento"))


def _seguir_prepara(frase, ctx):
    jug = ctx.get("jugador")
    if jug is None:
        if ctx.get("candidatos"):
            nombres = ", ".join(str(getattr(x, "name", "") or "") for x in ctx["candidatos"][:5])
            return f"¿A cuál te refieres? {nombres}.", None
        return "Dime a quién quieres seguir, con su nombre.", None
    return (f"Voy a poner a {getattr(jug, 'name', '')} en el seguimiento de la temporada. "
            "¿Confirmo?"), {"player_id": int(jug.id)}


def _seguir_ejecuta(datos, ctx):
    from football.models import Player, SeasonWatch

    p = Player.objects.filter(id=int(datos["player_id"])).first()
    if p is None:
        return False, "Ya no encuentro a ese jugador."
    obj, creado = SeasonWatch.objects.get_or_create(
        player=p,
        defaults={"created_by": ctx.get("usuario"), "reason": "Añadido desde el asistente"},
    )
    if not creado and not obj.is_active:
        obj.is_active = True
        obj.save(update_fields=["is_active"])
        creado = True
    return True, (f"{p.name} {'ya estaba' if not creado else 'entra'} en el seguimiento."
                  "\n\nVer: /coach/seguimiento/")


CATALOGO = (
    {"clave": "mover_bloque", "reconoce": _mover_bloque_reconoce,
     "prepara": _mover_bloque_prepara, "ejecuta": _mover_bloque_ejecuta},
    {"clave": "borrar_tarea", "reconoce": _borrar_reconoce,
     "prepara": _borrar_prepara, "ejecuta": _borrar_ejecuta},
    {"clave": "restaurar_tarea", "reconoce": _restaurar_reconoce,
     "prepara": _restaurar_prepara, "ejecuta": _restaurar_ejecuta},
    {"clave": "seguir_jugador", "reconoce": _seguir_reconoce,
     "prepara": _seguir_prepara, "ejecuta": _seguir_ejecuta},
)


def detectar(frase):
    """La primera acción que reconozca la frase, o None."""
    for accion in CATALOGO:
        try:
            if accion["reconoce"](frase):
                return accion
        except Exception:
            logger.debug("accion %s fallo al reconocer", accion.get("clave"), exc_info=True)
    return None


def por_clave(clave):
    for accion in CATALOGO:
        if accion["clave"] == str(clave or ""):
            return accion
    return None
