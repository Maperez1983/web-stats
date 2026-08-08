"""Las respuestas del asistente que NO necesitan modelo ni diagnóstico del sistema.

Por qué existe: el chat tenía dos velocidades. Las preguntas de datos del club las contesta un
enrutador por palabras clave en ~100 ms, y funcionan bien. Todo lo demás caía en el guardián,
que es un diagnosticador de sistema: tardaba 6-15 s y respondía con un parte del servidor
aunque le preguntaras cómo se crea una tarea.

Aquí viven las tres intenciones que faltaban y que el sistema YA sabe resolver, solo que nadie
las había conectado al chat:

  - LLEVAME A: navegar a una zona. Antes funcionaba, pero pasando por el guardián: 5,7 s.
  - BUSCA: el buscador global (`/api/search/`) ya indexa sesiones, tareas y atajos.
  - SUGIÉREME TAREAS: el recomendador de la biblioteca lleva escrito y poblado (288 tareas
    indexadas) y solo se usaba desde una pantalla.

Nada de esto sale del servidor ni cuesta dinero: son consultas a tu propia base de datos.
"""
from __future__ import annotations

import re
import unicodedata


def _sin_tildes(texto: str) -> str:
    crudo = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", crudo) if not unicodedata.combining(c))


# Zonas del programa. La clave es el nombre de la ruta; los sinónimos son cómo las llama él.
# Se escriben sin tildes porque la pregunta se normaliza antes de comparar.
ZONAS = (
    ("sessions", "Entrenamiento", "/coach/sesiones/",
     ("entrenamiento", "entrenamientos", "sesion", "sesiones", "entreno", "entrenos")),
    ("coach-detail", "Entrenador", "/coach/",
     ("inicio", "principal", "entrenador", "home", "portada")),
    ("squad", "Plantilla", "/coach/plantilla/",
     ("plantilla", "jugadores", "equipo", "roster")),
    ("matches", "Partidos", "/coach/partidos/",
     ("partido", "partidos", "calendario", "competicion", "competiciones")),
    ("analysis", "Análisis", "/coach/analisis/",
     ("analisis", "video", "videos", "video-analisis", "videoanalisis", "clips")),
    ("library", "Biblioteca de tareas", "/coach/sesiones/?tab=library",
     ("biblioteca", "tareas", "ejercicios", "repositorio")),
    ("season-watch", "Seguimiento", "/coach/seguimiento/",
     ("seguimiento", "ojeados", "ojeo", "scouting", "seguidos")),
    ("injuries", "Lesiones", "/coach/plantilla/",
     ("lesiones", "enfermeria", "parte medico")),
)

_VERBOS_IR = ("llevame", "llevame a", "ir a", "abre", "abreme", "vete a", "ve a", "entra en",
              "quiero ir a", "muestrame", "ensename", "donde esta", "donde estan")

# ORDENES. El asistente NO las ejecuta, y esto es a proposito: escribir en la ficha de un
# jugador porque una frase ha encajado con unas palabras es justo el fallo que tenia el
# guardian -reparaba datos del club porque alguien preguntaba algo-. Lo que hace es reconocer
# la orden y llevarte a la pantalla donde se hace, en un clic.
#
# Y hay un motivo mas inmediato: "marca a Nico como lesionado" contestaba con la LISTA de
# lesionados, porque la palabra "lesionado" la leia como consulta. Nico ya estaba lesionado,
# asi que la respuesta parecia una confirmacion de algo que no habia pasado. Eso es peor que
# no saber hacerlo.
_PALABRAS_ORDEN = ("marca", "marcar", "anota", "anotar", "apunta", "apuntar", "pon", "poner",
                   "registra", "registrar", "quita", "quitar", "borra", "borrar", "cambia",
                   "cambiar", "convoca", "convocar", "da de baja", "da de alta")
_VERBOS_BUSCAR = ("busca", "buscar", "buscame", "encuentra", "encuentrame", "localiza")
_VERBOS_SUGERIR = ("sugiere", "sugiereme", "recomienda", "recomiendame", "proponme", "propon",
                   "dame tareas", "dame ejercicios", "que tareas", "que ejercicios")


# Palabras de relleno al principio del resto ("a la biblioteca" -> "biblioteca").
_RELLENO = ("a", "al", "la", "el", "los", "las", "de", "del", "un", "una", "unas", "unos",
            "por", "para", "sobre", "mi", "mis",
            # "sugiereme TAREAS DE finalizacion" -> lo que importa es "finalizacion". Sin quitar
            # estas, el recomendador puntuaba contra "tareas" y "de" y no encontraba nada.
            "tarea", "tareas", "ejercicio", "ejercicios", "sesion", "sesiones", "trabajo")


def _limpiar_resto(texto: str) -> str:
    """Quita signos y las palabras de relleno del principio.

    OJO: no vale `strip(" a")`, que borra LETRAS sueltas de los extremos: con eso
    "a la biblioteca" acababa en "la bibliotec" y dejaba de emparejar con "biblioteca".
    """
    palabras = [p for p in re.split(r"[\s?¿.,:;!¡]+", texto or "") if p]
    while palabras and palabras[0] in _RELLENO:
        palabras.pop(0)
    return " ".join(palabras).strip()


def detectar_intencion(pregunta: str) -> tuple[str, str]:
    """Devuelve (intencion, resto). Intención vacía = no es para este enrutador."""
    q = _sin_tildes(pregunta)
    if not q:
        return "", ""

    # Las ORDENES se miran ANTES que nada. Si no, "marca a Nico como lesionado" cae en el
    # enrutador de datos por la palabra "lesionado" y responde con la lista, como si lo
    # hubiera hecho.
    if any(re.search(r"(?:^|\s)" + re.escape(v) + r"(?:\s|$)", q) for v in _PALABRAS_ORDEN):
        return "orden", q

    # Por longitud descendente y con frontera de palabra: si no, "sugiere" corta dentro de
    # "sugiereme" y deja un "me" pegado al principio de lo que se busca.
    for intencion, verbos in (("sugerir", _VERBOS_SUGERIR),
                              ("buscar", _VERBOS_BUSCAR),
                              ("ir", _VERBOS_IR)):
        for verbo in sorted(verbos, key=len, reverse=True):
            m = re.search(r"(?:^|\s)" + re.escape(verbo) + r"(?:\s|$)", q)
            if m:
                return intencion, _limpiar_resto(q[m.end():])
    return "", ""


def resolver_zona(texto: str):
    """Empareja lo que ha escrito con una zona del programa."""
    q = _sin_tildes(texto)
    if not q:
        return None
    mejor = None
    for nombre, etiqueta, url, sinonimos in ZONAS:
        for s in sinonimos:
            if s in q:
                # Gana el sinónimo más largo: "biblioteca de tareas" antes que "tareas".
                if mejor is None or len(s) > mejor[0]:
                    mejor = (len(s), nombre, etiqueta, url)
    if mejor is None:
        return None
    return {"ruta": mejor[1], "etiqueta": mejor[2], "url": mejor[3]}


def respuesta_navegacion(texto: str):
    zona = resolver_zona(texto)
    if not zona:
        conocidas = ", ".join(sorted({z[1] for z in ZONAS}))
        return {
            "message": f"No sé a qué zona te refieres. Puedo llevarte a: {conocidas}.",
            "highlights": [z[1] for z in ZONAS][:4],
        }
    return {
        "message": f"Te llevo a {zona['etiqueta']}.\n\n{zona['etiqueta']}: {zona['url']}",
        "highlights": [zona["etiqueta"]],
        "ir_a": zona["url"],
    }


def _lineas_de_grupo(grupo, tope=4):
    filas = []
    for item in (grupo.get("items") or [])[:tope]:
        etiqueta = str(item.get("label") or item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if etiqueta:
            filas.append(f"· {etiqueta}" + (f" — {url}" if url else ""))
    return filas


def respuesta_busqueda(grupos, texto):
    """Formatea lo que devuelve el buscador global."""
    grupos = [g for g in (grupos or []) if isinstance(g, dict) and (g.get("items") or [])]
    if not grupos:
        return {"message": f"No he encontrado nada con «{texto}».", "highlights": []}
    partes = [f"Esto es lo que encuentro con «{texto}»:"]
    for g in grupos[:3]:
        titulo = str(g.get("label") or g.get("title") or "Resultados").strip()
        filas = _lineas_de_grupo(g)
        if filas:
            partes.append(f"\n{titulo}:\n" + "\n".join(filas))
    return {
        "message": "\n".join(partes),
        "highlights": [str(g.get("label") or "") for g in grupos[:4]],
    }


def _campo(tarea, *nombres):
    """Lee un campo venga como diccionario o como objeto del modelo.

    El recomendador devuelve OBJETOS SessionTask, no diccionarios. Filtrar por `isinstance
    dict` los tiraba todos y el asistente contestaba "no encuentro tareas" mientras el
    recomendador se las estaba dando. Se ve en cuanto se prueba con datos reales.
    """
    for nombre in nombres:
        if isinstance(tarea, dict):
            valor = tarea.get(nombre)
        else:
            valor = getattr(tarea, nombre, None)
        if valor not in (None, ""):
            return valor
    return None


def respuesta_sugerencias(tareas, texto, total=None, url_todas=""):
    tareas = [t for t in (tareas or []) if t is not None]
    if not tareas:
        return {
            "message": f"No encuentro tareas de «{texto}» en tu biblioteca.",
            "highlights": [],
        }
    filas, titulos = [], []
    for t in tareas[:5]:
        titulo = str(_campo(t, "title", "titulo") or "").strip()
        tid = _campo(t, "id", "task_id")
        if not titulo:
            continue
        titulos.append(titulo)
        porque = str(_campo(t, "ai_trainer_why") or "").strip()
        fila = f"· {titulo}"
        if tid:
            fila += f" — /coach/sesiones/tarea/{int(tid)}/"
        if porque:
            fila += f"\n   ({porque})"
        filas.append(fila)
    if not filas:
        return {"message": f"No encuentro tareas de «{texto}» en tu biblioteca.", "highlights": []}
    # Decir CUANTAS hay en total. El recomendador propone seis como mucho y ademas limita
    # cuantas caen de la misma familia -seis rondos casi iguales no es una recomendacion-, asi
    # que sin este dato parece que solo tienes cinco tareas de rondo cuando tienes doce.
    cabecera = f"Tareas de tu biblioteca para «{texto}»"
    try:
        if total and int(total) > len(filas):
            cabecera += f" ({len(filas)} de {int(total)}, elegidas por variedad)"
    except Exception:
        pass
    cuerpo = "\n".join(filas)
    if url_todas:
        cuerpo += f"\n\nVer todas: {url_todas}"
    return {
        "message": f"{cabecera}:\n{cuerpo}",
        "highlights": [t[:40] for t in titulos[:4]],
    }


# --- ORDENES -------------------------------------------------------------------------------
# Que hace y que NO hace: reconoce lo que le pides, te dice que no lo va a hacer solo, y te
# deja en la pantalla donde se hace. Nada de escribir en la ficha de nadie por haber acertado
# unas palabras: eso es exactamente lo que hacia el guardian con las reparaciones.

_TEMAS = (
    ("asistencia", ("ausente", "ausencia", "presente", "asiste", "asistencia",
                    "no viene", "no vino", "no ha venido", "no asistio", "no asistió",
                    "falta", "falto", "faltó", "vino", "entreno", "entrenamiento",
                    "convoca", "convocatoria")),
    ("lesion", ("lesion", "lesionado", "lesionada", "baja", "molestia", "recaida")),
    ("evaluacion", ("evaluacion", "valoracion", "nota", "puntua", "califica")),
)


def tema_de_la_orden(texto: str) -> str:
    q = _sin_tildes(texto)
    for tema, palabras in _TEMAS:
        if any(p in q for p in palabras):
            return tema
    return ""


def respuesta_orden(texto, *, tema="", jugador=None, sesion=None):
    """Reconoce la orden, dice claramente que no la ejecuta y lleva a la pantalla."""
    quien = str(getattr(jugador, "name", "") or "").strip()
    destino, comoSeHace = "", ""

    if tema == "asistencia":
        if sesion is not None:
            fecha = ""
            try:
                fecha = sesion.session_date.strftime("%d/%m") if sesion.session_date else ""
            except Exception:
                fecha = ""
            destino = f"/coach/sesiones/sesion/{int(sesion.id)}/"
            comoSeHace = (f"En la sesión{(' del ' + fecha) if fecha else ''}, en la lista de "
                          f"asistencia, cambia el desplegable de{(' ' + quien) if quien else ' ese jugador'}.")
        else:
            destino = "/coach/sesiones/"
            comoSeHace = "Abre la sesión y cambia el desplegable de asistencia del jugador."
    elif tema == "lesion":
        destino = (f"/player/{int(jugador.id)}/" if jugador is not None else "/coach/plantilla/")
        comoSeHace = (f"En la ficha de{(' ' + quien) if quien else ' ese jugador'}, en Lesiones, "
                      "«Nuevo parte». Ahí se registra la baja y la fecha.")
    elif tema == "evaluacion":
        destino = (f"/player/{int(jugador.id)}/" if jugador is not None else "/coach/plantilla/")
        comoSeHace = "En la ficha del jugador, pestaña de valoraciones."
    else:
        return {
            "message": ("Eso es una orden, y de momento no ejecuto cambios: solo consulto y te "
                        "llevo. Dime qué pantalla necesitas y te abro la puerta."),
            "highlights": ["Solo lectura"],
        }

    cabecera = "No lo hago yo: no escribo en las fichas."
    return {
        "message": f"{cabecera}\n\n{comoSeHace}\n\nAbrir: {destino}",
        "highlights": [quien or "Jugador", "Solo lectura"],
        "ir_a": destino,
    }
