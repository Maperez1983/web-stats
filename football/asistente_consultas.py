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

DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def dia_corto(fecha):
    """"mar 04/08". El strftime del servidor da "Tue": el locale no es de fiar."""
    try:
        return f"{DIAS_CORTOS[fecha.weekday()]} {fecha.strftime('%d/%m')}"
    except Exception:
        return ""


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

    # "que HICE el martes" es el martes que ya paso; "que hago el martes", el que viene. Sin
    # esto, preguntando un viernes por lo que hiciste el martes te contestaba con el siguiente.
    en_pasado = any(p in q for p in ("hice", "hicimos", "hiciste", "entrene", "entrenamos",
                                     "fue", "vino", "vinieron", "falto", "faltaron", "trabaje",
                                     "trabajamos", "pasado", "pasada", "ultimo", "ultima"))

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
        if not delDia:
            return None
        if en_pasado:
            pasadas = [s for s in delDia if s.session_date <= hoy]
            if pasadas:
                return max(pasadas, key=lambda s: s.session_date)
        return min(delDia, key=lambda s: abs((s.session_date - hoy).days))

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
        lineas.append(f"· {dia_corto(s.session_date)}"
                      + (f" {hora}" if hora else "") + (f" — {foco}" if foco else ""))
    return {
        "message": f"Tienes {len(sesiones)} {'sesiones' if len(sesiones) != 1 else 'sesión'} {cuando}:\n"
                   + "\n".join(lineas) + "\n\nVer: /coach/sesiones/",
        "highlights": [f"{len(sesiones)} sesiones"],
    }


def _jugador_nombrado(frase, equipo):
    """El jugador que nombra la frase. Con frontera de palabra: hay uno llamado Reno y
    encajaba dentro de "entreno"."""
    from football.models import Player

    q = _sin_tildes(frase)
    encontrados = []
    for p_ in Player.objects.filter(team=equipo, is_active=True).only(
        "id", "name", "full_name", "nickname", "number", "position", "birth_date"
    ):
        for cand in (p_.name, p_.full_name, p_.nickname):
            cand = str(cand or "").strip()
            if len(cand) >= 3 and re.search(r"\b" + re.escape(_sin_tildes(cand)) + r"\b", q):
                encontrados.append(p_)
                break
    return encontrados


def es_pregunta_jugador(frase):
    q = _sin_tildes(frase)
    # Se exige una FORMA DE PREGUNTAR, no solo el nombre: "pon a Harley en seguimiento" lleva
    # su nombre y es una orden, no una consulta.
    return any(p in q for p in ("como va", "que tal esta", "que tal va", "como esta", "ficha de",
                                "informacion de", "info de", "datos de", "cuantos goles",
                                "cuantas tarjetas", "cuantos minutos", "como lleva"))


def responder_jugador(frase, equipo):
    from football.models import PlayerInjuryRecord

    encontrados = _jugador_nombrado(frase, equipo)
    if not encontrados:
        return {"message": "No sé de qué jugador hablas. Dime su nombre tal cual aparece en la "
                           "plantilla.", "highlights": []}
    if len(encontrados) > 1:
        nombres = ", ".join(str(getattr(x, "name", "") or "") for x in encontrados[:5])
        return {"message": f"¿A cuál te refieres? {nombres}.", "highlights": ["Hay más de uno"]}

    p_ = encontrados[0]
    datos = []
    if p_.number:
        datos.append(f"dorsal {p_.number}")
    if p_.position:
        datos.append(str(p_.position))
    try:
        if p_.birth_date:
            from django.utils import timezone

            hoy = timezone.localdate()
            edad = hoy.year - p_.birth_date.year - (
                (hoy.month, hoy.day) < (p_.birth_date.month, p_.birth_date.day)
            )
            datos.append(f"{edad} años")
    except Exception:
        pass

    # Lo primero que quiere saber un entrenador: si puede contar con él.
    estado = "disponible"
    try:
        abierta = (
            PlayerInjuryRecord.objects.filter(player=p_, is_active=True)
            .order_by("-id")
            .first()
        )
        if abierta is not None:
            detalle = str(getattr(abierta, "description", "") or getattr(abierta, "injury_type", "") or "").strip()
            estado = "LESIONADO" + (f" ({detalle[:40]})" if detalle else "")
    except Exception:
        pass

    cabecera = f"{p_.name}" + (f" — {', '.join(datos)}" if datos else "")
    return {
        "message": f"{cabecera}\nEstado: {estado}\n\nFicha: /player/{int(p_.id)}/",
        "highlights": [str(p_.name or ""), estado[:20]],
    }


# --- Partidos --------------------------------------------------------------------------------

def _es_nuestro(equipo, otro):
    try:
        return otro is not None and int(getattr(otro, "id", 0)) == int(getattr(equipo, "id", 0))
    except Exception:
        return False


def _rival_de(partido, equipo):
    otro = partido.away_team if _es_nuestro(equipo, partido.home_team) else partido.home_team
    return str(getattr(otro, "display_name", "") or getattr(otro, "name", "") or "rival")


def _casa_o_fuera(partido, equipo):
    return "en casa" if _es_nuestro(equipo, partido.home_team) else "fuera"


def _partidos_del_equipo(equipo):
    from django.db.models import Q

    from football.models import Match

    return Match.objects.select_related("home_team", "away_team").filter(
        Q(home_team=equipo) | Q(away_team=equipo)
    )


def es_pregunta_proximo_partido(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("contra quien", "con quien", "proximo partido", "siguiente partido",
                                 "cuando jugamos", "cuando es el partido", "que partido"))
            or ("jugamos" in q and any(d in q for d, _ in DIAS)))


def responder_proximo_partido(frase, equipo):
    from django.utils import timezone

    hoy = timezone.localdate()
    prox = (
        _partidos_del_equipo(equipo)
        .filter(date__gte=hoy)
        .order_by("date", "kickoff_time", "id")
        .first()
    )
    if prox is None:
        return {"message": "No tienes ningún partido por delante en el calendario.",
                "highlights": []}
    hora = prox.kickoff_time.strftime("%H:%M") if getattr(prox, "kickoff_time", None) else ""
    donde = str(getattr(prox, "location", "") or "").strip()
    partes = [f"{_rival_de(prox, equipo)} ({_casa_o_fuera(prox, equipo)})",
              dia_corto(prox.date) if prox.date else ""]
    if hora:
        partes.append(hora)
    if donde:
        partes.append(donde[:40])
    torneo = str(getattr(prox, "tournament_name", "") or "").strip()
    cabecera = "Próximo partido: " + " · ".join([x for x in partes if x])
    if torneo:
        cabecera += f"\n{torneo[:50]}"
    return {"message": cabecera + f"\n\nVer: /coach/partidos/",
            "highlights": [_rival_de(prox, equipo)[:30]]}


def es_pregunta_ultimo_partido(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("como quedo", "como quedamos", "que tal el partido",
                                 "resultado", "ultimo partido", "como fue el partido",
                                 "ganamos", "perdimos", "empatamos"))
            and "proximo" not in q)


def responder_ultimo_partido(frase, equipo):
    from django.utils import timezone

    hoy = timezone.localdate()
    # "El ultimo partido" es el ultimo JUGADO, no el ultimo del calendario. Preguntando el
    # mismo dia del partido, el de hoy aun no se ha jugado y contestaba "todavia no tiene
    # resultado" cuando lo que quieres saber es como quedo el de la semana pasada.
    jugados = [
        m for m in _partidos_del_equipo(equipo).filter(date__lte=hoy).order_by("-date", "-id")[:12]
        if m.home_score is not None and m.away_score is not None
    ]
    ult = jugados[0] if jugados else (
        _partidos_del_equipo(equipo).filter(date__lte=hoy).order_by("-date", "-id").first()
    )
    if ult is None:
        return {"message": "No encuentro ningún partido jugado.", "highlights": []}
    nuestros = ult.home_score if _es_nuestro(equipo, ult.home_team) else ult.away_score
    suyos = ult.away_score if _es_nuestro(equipo, ult.home_team) else ult.home_score
    if nuestros is None or suyos is None:
        return {"message": f"El partido contra {_rival_de(ult, equipo)} "
                           f"({dia_corto(ult.date)}) todavía no tiene resultado."
                           f"\n\nCerrarlo: /coach/partidos/",
                "highlights": ["Sin resultado"]}
    # Se dice el signo, que es lo primero que se mira.
    if nuestros > suyos:
        signo = "Ganamos"
    elif nuestros < suyos:
        signo = "Perdimos"
    else:
        signo = "Empatamos"
    return {
        "message": (f"{signo} {int(nuestros)}-{int(suyos)} contra {_rival_de(ult, equipo)} "
                    f"({_casa_o_fuera(ult, equipo)}, {dia_corto(ult.date)})."
                    f"\n\nVer: /coach/partidos/"),
        "highlights": [signo, f"{int(nuestros)}-{int(suyos)}"],
    }


# --- Video -----------------------------------------------------------------------------------

def es_pregunta_videos(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("video", "videos", "clip", "clips", "grabacion", "grabaciones"))
            and any(p in q for p in ("cuantos", "cuantas", "que ", "tengo", "hay", "lista")))


def responder_videos(frase, equipo):
    from football.models import AnalystVideoFolder, RivalVideo, VideoClip

    videos = RivalVideo.objects.filter(team=equipo).count()
    clips = VideoClip.objects.filter(team=equipo).count()
    carpetas = list(
        AnalystVideoFolder.objects.filter(team=equipo).order_by("-created_at")[:6]
    )
    if not videos and not clips and not carpetas:
        return {"message": "Todavía no tienes vídeos.\n\nSubirlos: /coach/analisis/",
                "highlights": []}
    lineas = [f"Tienes {videos} vídeo{'s' if videos != 1 else ''} y {clips} clip{'s' if clips != 1 else ''}."]
    if carpetas:
        lineas.append("Carpetas: " + " · ".join(str(c.name or "")[:28] for c in carpetas))
    return {"message": "\n".join(lineas) + "\n\nVer: /coach/analisis/",
            "highlights": [f"{videos} vídeos", f"{clips} clips"]}


# --- Clasificacion, biblioteca y goleadores ---------------------------------------------------

def es_pregunta_clasificacion(frase):
    q = _sin_tildes(frase)
    return any(p in q for p in ("clasificacion", "que rivales", "quien va primero", "en que puesto",
                                "posicion en la liga", "tabla", "como vamos en la liga",
                                "rivales de la liga", "rivales tengo"))


def responder_clasificacion(frase, equipo):
    from football.models import TeamStanding

    mia = TeamStanding.objects.filter(team=equipo).order_by("-last_updated").first()
    if mia is None or not getattr(mia, "group_id", None):
        return {"message": "No tengo la clasificación de tu grupo cargada todavía."
                           "\n\nVer: /coach/partidos/", "highlights": []}
    filas = list(
        TeamStanding.objects.select_related("team")
        .filter(group_id=mia.group_id, season=mia.season)
        .order_by("position")[:20]
    )
    if not filas:
        return {"message": "No tengo la clasificación cargada.", "highlights": []}
    lineas = []
    for f in filas:
        marca = " ←" if int(getattr(f, "team_id", 0)) == int(equipo.id) else ""
        lineas.append(f"{int(f.position or 0):2}. {str(getattr(f.team, 'name', '') or '')[:26]}"
                      f" — {int(f.points or 0)} pts{marca}")
    return {
        "message": f"Clasificación ({len(filas)} equipos):\n" + "\n".join(lineas)
                   + "\n\nVer: /coach/partidos/",
        "highlights": [f"{int(mia.position or 0)}º", f"{int(mia.points or 0)} pts"],
    }


def es_pregunta_cuantas_tareas(frase):
    q = _sin_tildes(frase)
    return (any(p in q for p in ("cuantas", "cuantos")) 
            and any(p in q for p in ("tarea", "tareas", "ejercicio", "ejercicios"))
            and "sesion" not in q)


def responder_cuantas_tareas(frase, equipo):
    from django.db.models import Q

    from football.models import SessionTask

    try:
        from football.library_sharing import ids_de_tareas_compartidas_de_un_equipo

        compartidas = set(ids_de_tareas_compartidas_de_un_equipo(equipo) or [])
    except Exception:
        compartidas = set()
    alcance = Q(session__microcycle__team=equipo)
    if compartidas:
        alcance |= Q(id__in=list(compartidas)[:2000])
    total = SessionTask.objects.filter(alcance, deleted_at__isnull=True).count()
    papelera = SessionTask.objects.filter(alcance, deleted_at__isnull=False).count()
    texto = f"Tienes {total} tarea{'s' if total != 1 else ''} disponibles"
    if papelera:
        texto += f" y {papelera} en la papelera"
    return {"message": texto + ".\n\nVer: /coach/sesiones/?tab=library",
            "highlights": [f"{total} tareas"]}


def es_pregunta_goleador(frase):
    q = _sin_tildes(frase)
    return any(p in q for p in ("goleador", "maximo goleador", "quien mas goles", "mas goles",
                                "quien lleva mas goles", "pichichi"))


def responder_goleador(frase, equipo):
    from django.db.models import Count

    from football.models import MatchEvent, Player

    ids = list(Player.objects.filter(team=equipo).values_list("id", flat=True))
    # Se cuenta del REGISTRO de acciones, que es la fuente que el llena: los goles apuntados
    # en directo o en la edicion del partido.
    filas = (
        MatchEvent.objects.filter(player_id__in=ids)
        .filter(event_type__icontains="gol")
        .values("player_id")
        .annotate(n=Count("id"))
        .order_by("-n")[:5]
    )
    if not filas:
        return {"message": "No hay goles apuntados en el registro de acciones todavía.",
                "highlights": []}
    porId = {p.id: p for p in Player.objects.filter(id__in=[f["player_id"] for f in filas])}
    lineas = [f"· {str(getattr(porId.get(f['player_id']), 'name', '') or '?')} — {f['n']} gol"
              f"{'es' if f['n'] != 1 else ''}" for f in filas]
    return {"message": "Máximos goleadores:\n" + "\n".join(lineas),
            "highlights": [str(getattr(porId.get(filas[0]["player_id"]), "name", "") or "")]}


CONSULTAS = (
    (es_pregunta_asistencia, responder_asistencia),
    (es_pregunta_tareas_de_sesion, responder_tareas_de_sesion),
    (es_pregunta_cuantas_sesiones, responder_cuantas_sesiones),
    (es_pregunta_jugador, responder_jugador),
    # El ULTIMO antes que el PROXIMO: "como quedo el ultimo partido" lleva la palabra
    # "partido" y la de proximo la miraria tambien.
    (es_pregunta_ultimo_partido, responder_ultimo_partido),
    (es_pregunta_proximo_partido, responder_proximo_partido),
    (es_pregunta_videos, responder_videos),
    (es_pregunta_clasificacion, responder_clasificacion),
    (es_pregunta_goleador, responder_goleador),
    # La de las tareas va la ULTIMA: "cuantas tareas tiene la sesion del martes" es una
    # pregunta de la sesion, no del total de la biblioteca.
    (es_pregunta_cuantas_tareas, responder_cuantas_tareas),
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
