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

# Lo ultimo que miro el buscador de tareas. Existe porque llevo seis correcciones a ciegas
# sobre la misma comparacion: cuando el asistente propone una tarea rara hay que poder ver QUE
# candidatas encontro y con que texto comparo, no adivinar el criterio.
ULTIMA_BUSQUEDA = {"frase": "", "palabras": [], "en_alcance": 0, "candidatas": [], "elegida": ""}


def sin_tildes(texto: str) -> str:
    crudo = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", crudo) if not unicodedata.combining(c))


def clave_texto(texto: str) -> str:
    """Sin tildes, en minusculas y con TODO lo que no sea letra o numero como un solo espacio.

    Hace falta para comparar titulos con lo que escribe el usuario: un titulo guardado como
    "RONDO 8  x 2" -con dos espacios, o con un espacio duro pegado desde un PDF- no encajaba
    dentro de "borra la tarea Rondo 8 x 2" y el asistente proponia otra tarea distinta.
    """
    return " ".join(re.split(r"[^a-z0-9]+", sin_tildes(texto))).strip()


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


def _fecha_de(tarea):
    """dd/mm de la sesion de la tarea, o ''."""
    try:
        f = tarea.session.session_date
        return f.strftime("%d/%m") if f else ""
    except Exception:
        return ""


def _fecha_en_la_frase(frase):
    """Una fecha dicha como 16/09 o 16-9. Solo dia y mes: es como se habla."""
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", str(frase or ""))
    if not m:
        return ""
    return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"


def etiqueta_tarea(tarea):
    """Como se nombra una tarea cuando hay que distinguirla de otra igual."""
    titulo = str(getattr(tarea, "title", "") or "").strip()[:40]
    fecha = _fecha_de(tarea)
    return f"{titulo} ({fecha})" if fecha else titulo


def _tarea_nombrada(frase, equipo):
    """La tarea a la que se refiere, buscando su título dentro de la frase.

    Devuelve (tarea, candidatas). Si hay varias, NO elige: quien llama pregunta.
    """
    from django.db.models import Q

    from football.models import SessionTask

    q = clave_texto(frase)
    # Se BUSCA en la base de datos por las palabras de la frase, no se recorren "las ultimas
    # 400": la tarea que pides puede ser antigua. Medido en produccion: "borra la tarea Rondo 8
    # x 2" no la encontraba porque su id quedaba fuera del corte, y acababa proponiendo otra.
    # SE BUSCA EL TITULO, no se traen tareas para compararlas. Traer "las N mas recientes" y
    # comparar en Python siempre deja fuera lo antiguo: con el corte en 200 no entraba la tarea
    # que pedias -id 385- y el asistente proponia otra parecida. Aqui se generan los trozos de
    # la frase (de mas largo a mas corto) y se pregunta a la base de datos cual de ellos ES el
    # titulo de una tarea. Sin cortes y sin sorpresas.
    palabras = [p_ for p_ in q.split(" ") if p_]
    if not palabras:
        return None, []
    trozos = []
    for ini in range(len(palabras)):
        for fin in range(len(palabras), ini, -1):
            if fin - ini > 10:
                continue
            trozo = " ".join(palabras[ini:fin])
            if len(trozo) >= 4:
                trozos.append(trozo)
    trozos = sorted(set(trozos), key=len, reverse=True)[:40]

    filtro = Q()
    for trozo in trozos:
        filtro |= Q(title__iexact=trozo)

    try:
        from football.library_sharing import ids_de_tareas_compartidas_de_un_equipo

        compartidas = set(ids_de_tareas_compartidas_de_un_equipo(equipo) or [])
    except Exception:
        compartidas = set()
    alcance = Q(session__microcycle__team=equipo)
    if compartidas:
        alcance |= Q(id__in=list(compartidas)[:2000])

    candidatas = list(
        SessionTask.objects.select_related("session__microcycle")
        .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        .filter(alcance, deleted_at__isnull=True)
        .filter(filtro)
    )
    ULTIMA_BUSQUEDA["frase"] = q
    ULTIMA_BUSQUEDA["palabras"] = trozos[:5]
    ULTIMA_BUSQUEDA["en_alcance"] = len(candidatas)
    ULTIMA_BUSQUEDA["candidatas"] = [str(getattr(t, "title", "") or "")[:40] for t in candidatas[:8]]
    # Si varias comparten titulo, se distinguen por la FECHA de su sesion. Tiene tres tareas
    # llamadas exactamente "RONDO 8 x 2": sin esto, o eliges una al azar o preguntas con tres
    # opciones identicas, que es igual de inutil.
    fecha_pedida = _fecha_en_la_frase(frase)
    if fecha_pedida and len(candidatas) > 1:
        porFecha = [t for t in candidatas if _fecha_de(t) == fecha_pedida]
        if porFecha:
            candidatas = porFecha

    # GANA EL TITULO MAS LARGO. Con una tarea llamada "RONDO" y otra "Rondo 8 x 2", pedir la
    # segunda hacia que encajaran las dos, y quedarse con cualquiera es apuntar a la equivocada:
    # medido en produccion, "borra la tarea Rondo 8 x 2" proponia borrar "RONDO". El titulo mas
    # largo es el mas especifico. Si hay empate, no se elige: se pregunta.
    if not candidatas:
        return None, []
    candidatas.sort(key=lambda t: len(str(getattr(t, "title", "") or "")), reverse=True)
    if len(candidatas) == 1:
        ULTIMA_BUSQUEDA["elegida"] = str(getattr(candidatas[0], "title", "") or "")[:40]
        return candidatas[0], candidatas
    largo0 = len(str(getattr(candidatas[0], "title", "") or ""))
    largo1 = len(str(getattr(candidatas[1], "title", "") or ""))
    if largo0 > largo1:
        ULTIMA_BUSQUEDA["elegida"] = str(getattr(candidatas[0], "title", "") or "")[:40]
        return candidatas[0], candidatas
    ULTIMA_BUSQUEDA["elegida"] = "(empate: se pregunta)"
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
            nombres = " · ".join(etiqueta_tarea(t) for t in candidatas[:5])
            return (f"Tienes varias con ese nombre: {nombres}. Dime la fecha, "
                    "por ejemplo «la del 16/09».", None)
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
            nombres = " · ".join(etiqueta_tarea(t) for t in candidatas[:5])
            return (f"Tienes varias con ese nombre: {nombres}. Dime la fecha, "
                    "por ejemplo «la del 16/09».", None)
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

    q = clave_texto(frase)
    candidatas = [
        t for t in SessionTask.objects
        .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        .filter(session__microcycle__team=ctx["equipo"], deleted_at__isnull=False)
        .order_by("-deleted_at")[:200]
        if len(clave_texto(str(t.title or ""))) >= 4 and clave_texto(str(t.title or "")) in q
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


# ---- duplicar una tarea ----------------------------------------------------------------------

def _duplicar_reconoce(frase):
    return dice(frase, "duplica", "duplicar", "copia", "copiar", "clona", "clonar")


def _duplicar_prepara(frase, ctx):
    tarea, candidatas = _tarea_nombrada(frase, ctx["equipo"])
    if tarea is None:
        if len(candidatas) > 1:
            nombres = " · ".join(etiqueta_tarea(t) for t in candidatas[:5])
            return f"Tienes varias con ese nombre: {nombres}. Dime la fecha.", None
        return "No sé qué tarea quieres duplicar. Dime su título tal cual.", None
    return f"Voy a duplicar «{tarea.title}». ¿Confirmo?", {"tarea_id": int(tarea.id)}


def _duplicar_ejecuta(datos, ctx):
    from football.models import SessionTask

    original = SessionTask.objects.filter(id=int(datos["tarea_id"])).first()
    if original is None:
        return False, "Esa tarea ya no está."
    # Copia por campos, sin `pk=None`+save: asi no se arrastran por accidente columnas que no
    # tocan (la portada embebida, el PDF) y se ve exactamente que se duplica.
    copia = SessionTask.objects.create(
        session=original.session,
        title=f"{original.title} (copia)"[:160],
        block=original.block,
        duration_minutes=original.duration_minutes,
        objective=original.objective,
        coaching_points=original.coaching_points,
        confrontation_rules=original.confrontation_rules,
        notes=original.notes,
        tactical_layout=original.tactical_layout,
    )
    return True, (f"Duplicada: «{copia.title}»."
                  f"\n\nAbrir: /coach/sesiones/tareas/{int(copia.id)}/editar/")


# ---- dejar de seguir a un jugador -------------------------------------------------------------

def _dejar_seguir_reconoce(frase):
    return contiene(frase, "dejar de seguir", "deja de seguir", "quitar del seguimiento",
                    "quita del seguimiento", "sacar del seguimiento")


def _dejar_seguir_prepara(frase, ctx):
    jug = ctx.get("jugador")
    if jug is None:
        return "Dime a quién quieres quitar del seguimiento.", None
    return (f"Voy a quitar a {getattr(jug, 'name', '')} del seguimiento. ¿Confirmo?",
            {"player_id": int(jug.id)})


def _dejar_seguir_ejecuta(datos, ctx):
    from football.models import Player, SeasonWatch

    p = Player.objects.filter(id=int(datos["player_id"])).first()
    if p is None:
        return False, "Ya no encuentro a ese jugador."
    n = SeasonWatch.objects.filter(player=p, is_active=True).update(is_active=False)
    if not n:
        return True, f"{p.name} no estaba en el seguimiento."
    return True, f"{p.name} sale del seguimiento.\n\nVer: /coach/seguimiento/"


# ---- cambiar la duracion de una tarea ---------------------------------------------------------

def _duracion_reconoce(frase):
    return (dice(frase, "duracion", "duración", "dura", "minutos", "min")
            and bool(re.search(r"\b\d{1,3}\b", sin_tildes(frase)))
            and dice(frase, "pon", "poner", "cambia", "cambiar", "deja", "dejar", "ajusta"))


def _duracion_prepara(frase, ctx):
    tarea, candidatas = _tarea_nombrada(frase, ctx["equipo"])
    if tarea is None:
        if len(candidatas) > 1:
            return ("Tienes varias con ese nombre: "
                    + " · ".join(etiqueta_tarea(t) for t in candidatas[:5])
                    + ". Dime la fecha.", None)
        return "No sé de qué tarea hablas. Dime su título tal cual.", None
    # El numero de los minutos, no el del titulo: se busca DESPUES del titulo en la frase.
    resto = clave_texto(frase).split(clave_texto(str(tarea.title or "")))[-1]
    m = re.search(r"\b(\d{1,3})\b", resto)
    if not m:
        return "No he visto los minutos. Dímelo así: «pon Rondo 6 vs 3 en 20 minutos».", None
    minutos = max(5, min(int(m.group(1)), 90))
    return (f"Voy a dejar «{tarea.title}» en {minutos} minutos (ahora tiene "
            f"{int(tarea.duration_minutes or 0)}). ¿Confirmo?",
            {"tarea_id": int(tarea.id), "minutos": minutos})


def _duracion_ejecuta(datos, ctx):
    from football.models import SessionTask

    t = SessionTask.objects.filter(id=int(datos["tarea_id"])).first()
    if t is None:
        return False, "Esa tarea ya no está."
    t.duration_minutes = int(datos["minutos"])
    t.save(update_fields=["duration_minutes"])
    return True, (f"«{t.title}» dura ahora {t.duration_minutes} minutos."
                  f"\n\nVer: /coach/sesiones/tarea/{int(t.id)}/")


# ---- crear una sesion --------------------------------------------------------------------------

DIAS_SEMANA = (("lunes", 0), ("martes", 1), ("miercoles", 2), ("jueves", 3),
               ("viernes", 4), ("sabado", 5), ("domingo", 6))


def _fecha_pedida(frase):
    """La fecha que dice la frase: «el jueves», «el 14/08», «mañana». None si no dice ninguna."""
    from datetime import timedelta

    from django.utils import timezone

    hoy = timezone.localdate()
    q = sin_tildes(frase)

    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b", q)
    if m:
        from datetime import date

        dia, mes = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3) or 0)
        if anio and anio < 100:
            anio += 2000
        try:
            f = date(anio or hoy.year, mes, dia)
            # Sin año, si ya paso se entiende el del año que viene: nadie crea una sesion para
            # una fecha que quedo atras.
            if not anio and f < hoy:
                f = date(hoy.year + 1, mes, dia)
            return f
        except Exception:
            return None

    if re.search(r"\bmanana\b", q):
        return hoy + timedelta(days=1)
    if re.search(r"\bhoy\b", q):
        return hoy
    if re.search(r"\bpasado manana\b", q):
        return hoy + timedelta(days=2)

    for nombre, indice in DIAS_SEMANA:
        if re.search(r"\b" + nombre + r"\b", q):
            # El PROXIMO que caiga en ese dia. Si hoy es jueves y dices "el jueves", es el de
            # dentro de siete dias: crear una sesion para hoy a toro pasado no tiene sentido.
            adelante = (indice - hoy.weekday()) % 7
            return hoy + timedelta(days=adelante or 7)
    return None


def _hora_pedida(frase):
    m = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", str(frase or ""))
    if not m:
        return None
    from datetime import time

    try:
        return time(int(m.group(1)), int(m.group(2)))
    except Exception:
        return None


def _crear_sesion_reconoce(frase):
    return (dice(frase, "crea", "crear", "programa", "programar", "monta", "montar", "añade", "anade")
            and contiene(frase, "sesion", "entreno", "entrenamiento"))


def _crear_sesion_prepara(frase, ctx):
    fecha = _fecha_pedida(frase)
    if fecha is None:
        return ("¿Para qué día? Dímelo así: «crea una sesión el jueves a las 18:30» "
                "o «crea un entreno el 14/08».", None)
    hora = _hora_pedida(frase)
    # Duracion: un numero seguido de "min", para no confundirlo con la hora.
    m = re.search(r"\b(\d{2,3})\s*(?:min|minutos)\b", sin_tildes(frase))
    minutos = max(30, min(int(m.group(1)), 180)) if m else 90

    from football.models import TrainingSession

    ya = TrainingSession.objects.filter(
        microcycle__team=ctx["equipo"], session_date=fecha
    ).exclude(microcycle__title__istartswith="Biblioteca ").count()

    aviso = ""
    if ya:
        # UNA sesion por dia es la norma de este club. No se bloquea, pero se avisa: crear la
        # segunda sin querer ensucia el calendario y cuesta verlo.
        aviso = f"\n\nOJO: ese día ya tienes {ya} sesión{'es' if ya != 1 else ''}."
    cuando = fecha.strftime("%d/%m/%Y")
    detalle = f"{cuando}" + (f" a las {hora.strftime('%H:%M')}" if hora else "") + f", {minutos} min"
    return (f"Voy a crear una sesión el {detalle}.{aviso} ¿Confirmo?",
            {"fecha": fecha.isoformat(), "hora": hora.strftime("%H:%M") if hora else "",
             "minutos": minutos, "equipo_id": int(ctx["equipo"].id)})


def _crear_sesion_ejecuta(datos, ctx):
    from datetime import datetime

    from django.db.models import Max

    from football.models import Team, TrainingSession
    from football.views import _resolve_week_microcycle_for_session

    equipo = Team.objects.filter(id=int(datos["equipo_id"])).first()
    if equipo is None:
        return False, "Ya no encuentro ese equipo."
    fecha = datetime.strptime(str(datos["fecha"]), "%Y-%m-%d").date()
    hora = None
    if datos.get("hora"):
        try:
            hora = datetime.strptime(str(datos["hora"]), "%H:%M").time()
        except Exception:
            hora = None
    # El microciclo lo resuelve la MISMA funcion que usa la pantalla: si aqui se creara uno
    # por libre, la sesion acabaria en una semana que no es la suya.
    micro = _resolve_week_microcycle_for_session(equipo, fecha)
    if micro is None:
        return False, "No he podido preparar el microciclo de esa semana."
    orden = (TrainingSession.objects.filter(microcycle=micro).aggregate(Max("order")).get("order__max") or 0) + 1
    ses = TrainingSession.objects.create(
        microcycle=micro,
        session_date=fecha,
        start_time=hora,
        duration_minutes=int(datos.get("minutos") or 90),
        focus="Entrenamiento",
        content="",
        order=orden,
    )
    return True, (f"Sesión creada el {fecha.strftime('%d/%m/%Y')}"
                  + (f" a las {hora.strftime('%H:%M')}" if hora else "")
                  + f".\n\nAbrir: /coach/sesiones/sesion/{int(ses.id)}/")


# ---- cortar clips de un partido a partir del registro de acciones -----------------------------
#
# LA IDEA, que es lo que la hace posible sin que ninguna IA mire el video: si los cornees estan
# en el REGISTRO DE ACCIONES con su minuto, y el video tiene marcado el saque inicial
# (`kickoff_ms`), entonces el momento exacto de cada corner en el video es una resta. No hay que
# reconocer nada: ya lo apuntaste tu durante el partido.

SEGUNDOS_ANTES = 8      # contexto: un corner empieza antes del saque
SEGUNDOS_DESPUES = 12


def _cortar_reconoce(frase):
    return (dice(frase, "corta", "cortar", "cortame", "saca", "sacame", "hazme", "genera")
            and contiene(frase, "clip", "clips", "corte", "cortes", "video", "jugadas"))


# Las marcas de la LINEA DE TIEMPO del estudio. Son otra cosa que el registro del partido:
# viven en el video, con el tiempo del video, y las pones tu analizando. Para ANALISIS es lo
# que vale: no dependen de que el partido sea tuyo ni de que este marcado el saque inicial.
MARCAS_ESTUDIO = (
    (("corner", "corners", "esquina", "esquinas", "abp", "estrategia", "balon parado"), "abp", "ABP"),
    (("gol", "goles"), "goal", "goles"),
    (("tiro", "tiros", "remate", "remates", "ocasion", "ocasiones"), "shot", "remates"),
    (("presion", "presiones"), "press", "presión"),
    (("perdida", "perdidas", "robo", "robos"), "turnover", "pérdidas"),
)


def _marca_estudio_pedida(frase):
    q = sin_tildes(frase)
    for palabras, clave, etiqueta in MARCAS_ESTUDIO:
        if any(re.search(r"\b" + p + r"\b", q) for p in palabras):
            return clave, etiqueta
    return "", ""


def _que_acciones(frase):
    """Qué acciones pide: devuelve (palabras a buscar, cómo llamarlas)."""
    q = sin_tildes(frase)
    catalogo = (
        (("corner", "corners", "esquina", "esquinas"), "córners"),
        (("gol", "goles"), "goles"),
        (("amarilla", "amarillas", "tarjeta", "tarjetas"), "tarjetas"),
        (("falta", "faltas"), "faltas"),
        (("tiro", "tiros", "remate", "remates", "ocasion", "ocasiones"), "remates"),
        (("penalti", "penaltis"), "penaltis"),
        (("cambio", "cambios"), "cambios"),
    )
    for palabras, etiqueta in catalogo:
        if any(re.search(r"\b" + p + r"\b", q) for p in palabras):
            return list(palabras), etiqueta
    return [], ""


def _partido_referido(frase, equipo):
    """El partido del que habla: por el nombre del rival, o el último jugado."""
    from django.db.models import Q
    from django.utils import timezone

    from football.models import Match

    q = sin_tildes(frase)
    partidos = Match.objects.select_related("home_team", "away_team").filter(
        Q(home_team=equipo) | Q(away_team=equipo)
    )
    for m in partidos.order_by("-date")[:60]:
        for lado in (m.home_team, m.away_team):
            nombre = sin_tildes(str(getattr(lado, "name", "") or ""))
            if len(nombre) >= 4 and nombre in q and int(getattr(lado, "id", 0)) != int(equipo.id):
                return m
    return partidos.filter(date__lte=timezone.localdate()).order_by("-date", "-id").first()


def _cortar_prepara(frase, ctx):
    from football.models import MatchEvent, RivalVideo

    palabras, etiqueta = _que_acciones(frase)
    if not palabras:
        return ("¿Qué quieres que corte? Dímelo así: «córtame los córners del partido contra "
                "La Mosca».", None)
    # PRIMERO el camino de ANALISIS: marcas puestas en la linea de tiempo del estudio. Son
    # tiempos del VIDEO, asi que valen para cualquier video -tambien el de un rival- y no
    # necesitan ni registro del partido ni saque inicial marcado. Registrar acciones en un
    # partido y analizar un video son dos cosas distintas y esta es la del analisis.
    clave_marca, etiqueta_marca = _marca_estudio_pedida(frase)
    if clave_marca:
        from football.models import RivalVideo, VideoTimelineEvent

        video_est = (
            RivalVideo.objects.filter(team=ctx["equipo"])
            .order_by("-is_base", "-id")
            .first()
        )
        if video_est is not None:
            marcas = list(
                VideoTimelineEvent.objects.filter(team=ctx["equipo"], video=video_est,
                                                  kind=clave_marca)
                .order_by("time_ms")[:40]
            )
            if marcas:
                return (f"Voy a crear {len(marcas)} clip{'s' if len(marcas) != 1 else ''} de "
                        f"{etiqueta_marca} del vídeo «{str(video_est.title or '')[:34]}», a partir "
                        "de las marcas que dejaste en la línea de tiempo. ¿Confirmo?",
                        {"video_id": int(video_est.id), "marca_ids": [int(m.id) for m in marcas],
                         "etiqueta": etiqueta_marca, "equipo_id": int(ctx["equipo"].id)})

    partido = _partido_referido(frase, ctx["equipo"])
    if partido is None:
        return "No encuentro ese partido.", None

    video = (
        RivalVideo.objects.filter(team=ctx["equipo"], match=partido)
        .order_by("-is_base", "-id")
        .first()
    )
    if video is None:
        return (f"El partido contra {_rival_del(partido, ctx['equipo'])} no tiene vídeo subido."
                "\n\nSubirlo: /coach/analisis/", None)
    if not getattr(video, "kickoff_ms", None):
        # Sin el saque inicial marcado no hay forma de traducir el minuto 34 a un momento del
        # video: el video empieza cuando le dio a grabar, no cuando pito el arbitro.
        return (f"El vídeo «{str(video.title or '')[:40]}» no tiene marcado el saque inicial, "
                "así que no sé a qué momento del vídeo corresponde cada minuto del partido.\n\n"
                "Márcalo en el estudio y te los corto: /coach/analisis/", None)

    filtro = None
    from django.db.models import Q

    for p_ in palabras:
        cond = Q(event_type__icontains=p_) | Q(kind__icontains=p_) | Q(observation__icontains=p_)
        filtro = cond if filtro is None else (filtro | cond)
    acciones = list(
        MatchEvent.objects.filter(match=partido).filter(filtro).order_by("minute", "id")[:40]
    )
    if not acciones:
        return (f"No hay {etiqueta} apuntados en el registro de ese partido. "
                "Sin registro no hay nada que cortar.", None)
    return (f"Voy a crear {len(acciones)} clip{'s' if len(acciones) != 1 else ''} de {etiqueta} "
            f"del partido contra {_rival_del(partido, ctx['equipo'])}, sobre el vídeo "
            f"«{str(video.title or '')[:34]}». ¿Confirmo?",
            {"video_id": int(video.id), "evento_ids": [int(a.id) for a in acciones],
             "etiqueta": etiqueta, "equipo_id": int(ctx["equipo"].id)})


def _rival_del(partido, equipo):
    try:
        otro = partido.away_team if int(partido.home_team_id) == int(equipo.id) else partido.home_team
        return str(getattr(otro, "name", "") or "rival")
    except Exception:
        return "rival"


def _cortar_ejecuta(datos, ctx):
    from football.models import MatchEvent, RivalVideo, Team, VideoClip, VideoTimelineEvent

    # Camino de ANALISIS: las marcas ya llevan el tiempo del video, no hay nada que calcular.
    if datos.get("marca_ids"):
        video = RivalVideo.objects.filter(id=int(datos["video_id"])).first()
        equipo = Team.objects.filter(id=int(datos["equipo_id"])).first()
        if video is None or equipo is None:
            return False, "Ya no encuentro ese vídeo."
        usuario = ctx.get("usuario") if getattr(ctx.get("usuario"), "is_authenticated", False) else None
        creados = 0
        for m in VideoTimelineEvent.objects.filter(id__in=datos["marca_ids"]).order_by("time_ms"):
            centro = int(getattr(m, "time_ms", 0) or 0)
            titulo = str(getattr(m, "label", "") or "").strip() or str(datos.get("etiqueta", "")).capitalize()
            try:
                VideoClip.objects.create(
                    team=equipo, video=video, owner_user=usuario, created_by=usuario,
                    title=f"{titulo} {centro // 60000}'"[:120],
                    in_ms=max(0, centro - SEGUNDOS_ANTES * 1000),
                    out_ms=centro + SEGUNDOS_DESPUES * 1000,
                )
                creados += 1
            except Exception:
                logger.debug("no se pudo crear un clip desde la linea de tiempo", exc_info=True)
        if not creados:
            return False, "No he podido crear los clips."
        return True, (f"Creados {creados} clips de {datos.get('etiqueta', '')} desde tus marcas."
                      "\n\nVer: /coach/analisis/")


    video = RivalVideo.objects.filter(id=int(datos["video_id"])).first()
    equipo = Team.objects.filter(id=int(datos["equipo_id"])).first()
    if video is None or equipo is None:
        return False, "Ya no encuentro ese vídeo."
    arranque = int(getattr(video, "kickoff_ms", 0) or 0)
    segunda = int(getattr(video, "second_half_ms", 0) or 0)
    acciones = list(MatchEvent.objects.filter(id__in=datos.get("evento_ids") or []).order_by("minute", "id"))
    creados = 0
    for a in acciones:
        minuto = int(getattr(a, "minute", 0) or 0)
        # La SEGUNDA PARTE tiene su propia marca: el descanso no dura lo mismo en el video que
        # en el partido, asi que del 45 en adelante se cuenta desde ahi.
        if minuto > 45 and segunda:
            base, desde = segunda, minuto - 45
        else:
            base, desde = arranque, minuto
        centro = base + desde * 60000
        entrada = max(0, centro - SEGUNDOS_ANTES * 1000)
        salida = centro + SEGUNDOS_DESPUES * 1000
        try:
            VideoClip.objects.create(
                team=equipo,
                video=video,
                owner_user=ctx.get("usuario") if getattr(ctx.get("usuario"), "is_authenticated", False) else None,
                title=f"{datos.get('etiqueta', 'Acción').capitalize()} {minuto}'"[:120],
                in_ms=int(entrada),
                out_ms=int(salida),
                created_by=ctx.get("usuario") if getattr(ctx.get("usuario"), "is_authenticated", False) else None,
            )
            creados += 1
        except Exception:
            logger.debug("no se pudo crear un clip", exc_info=True)
    if not creados:
        return False, "No he podido crear los clips."
    return True, (f"Creados {creados} clips de {datos.get('etiqueta', '')}. "
                  f"Cada uno arranca {SEGUNDOS_ANTES} s antes de la acción."
                  "\n\nVer: /coach/analisis/")


CATALOGO = (
    {"clave": "mover_bloque", "reconoce": _mover_bloque_reconoce,
     "prepara": _mover_bloque_prepara, "ejecuta": _mover_bloque_ejecuta},
    {"clave": "borrar_tarea", "reconoce": _borrar_reconoce,
     "prepara": _borrar_prepara, "ejecuta": _borrar_ejecuta},
    {"clave": "restaurar_tarea", "reconoce": _restaurar_reconoce,
     "prepara": _restaurar_prepara, "ejecuta": _restaurar_ejecuta},
    # "dejar de seguir" ANTES que "seguir": la segunda encaja dentro de la primera.
    {"clave": "dejar_seguir", "reconoce": _dejar_seguir_reconoce,
     "prepara": _dejar_seguir_prepara, "ejecuta": _dejar_seguir_ejecuta},
    {"clave": "seguir_jugador", "reconoce": _seguir_reconoce,
     "prepara": _seguir_prepara, "ejecuta": _seguir_ejecuta},
    {"clave": "duplicar_tarea", "reconoce": _duplicar_reconoce,
     "prepara": _duplicar_prepara, "ejecuta": _duplicar_ejecuta},
    {"clave": "duracion_tarea", "reconoce": _duracion_reconoce,
     "prepara": _duracion_prepara, "ejecuta": _duracion_ejecuta},
    {"clave": "crear_sesion", "reconoce": _crear_sesion_reconoce,
     "prepara": _crear_sesion_prepara, "ejecuta": _crear_sesion_ejecuta},
    {"clave": "cortar_clips", "reconoce": _cortar_reconoce,
     "prepara": _cortar_prepara, "ejecuta": _cortar_ejecuta},
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
