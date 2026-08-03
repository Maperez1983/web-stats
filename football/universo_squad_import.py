"""
Plantilla de un equipo propio desde Universo RFAF.

`fetch_universo_team_roster` ya existía pero sólo se usaba para RIVALES. Para el equipo
propio el club tenía que teclear a mano nombre por nombre. Aquí se casa lo que devuelve
Universo con los jugadores que ya están en la ficha, para completar lo que falte sin pisar
lo que el club haya escrito.

REGLA DEL CLUB: no se copia la plantilla de Universo. Sólo se completan los jugadores que ya
están dados de alta en la ficha y cuyo nombre casa. A los demás ni se les toca ni se les crea:
se listan por su nombre para que el club decida.

De cada fila se aprovecha todo lo que Universo mande —dorsal, posición, fecha de nacimiento,
nacionalidad y foto—, leyendo la fila cruda (`raw`) por si aparecen campos nuevos.
"""

from __future__ import annotations

import datetime
import logging
import re
import unicodedata


logger = logging.getLogger(__name__)

# Universo no documenta sus claves y cambian de un endpoint a otro: se buscan por lo que
# significan, no por un nombre exacto.
CLAVES_NACIMIENTO = ("fecha_nac", "fnacimiento", "nacimiento", "birth", "f_nac")
CLAVES_FOTO = ("foto", "imagen", "image", "photo", "avatar")
CLAVES_NACIONALIDAD = ("nacionalidad", "pais", "nationality")


def _texto(valor):
    return str(valor if valor is not None else "").strip()


def _buscar(raw, claves):
    """Primer valor cuya CLAVE contenga alguno de esos trozos. Devuelve '' si no hay."""
    if not isinstance(raw, dict):
        return ""
    for clave, valor in raw.items():
        nombre = _clave_llana(clave)
        if any(trozo in nombre for trozo in claves) and _texto(valor):
            return _texto(valor)
    return ""


def _clave_llana(texto):
    crudo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", crudo.lower())


def leer_fecha(valor):
    """Fecha de nacimiento en cualquiera de los formatos que suelta Universo. None si no cuela."""
    texto = _texto(valor)[:10]
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def url_de_foto(valor, base="https://www.universorfaf.es/"):
    """Universo devuelve unas veces la URL entera y otras una ruta suelta."""
    texto = _texto(valor)
    if not texto or texto.lower() in {"null", "none", "0"}:
        return ""
    if texto.startswith(("http://", "https://")):
        return texto
    if texto.startswith("//"):
        return "https:" + texto
    return base.rstrip("/") + "/" + texto.lstrip("/")


def _clave(nombre):
    """Nombre comparable: sin acentos, sin puntuación y con las palabras ordenadas."""
    crudo = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode("ascii")
    palabras = [p for p in re.split(r"[^a-zA-Z0-9]+", crudo.lower()) if p]
    return " ".join(sorted(palabras))


def nombre_persona(nombre):
    """Universo escribe "APELLIDOS, NOMBRE" en mayúsculas. En la ficha se lee al derecho."""
    texto = _texto(nombre)
    if not texto:
        return ""
    if "," in texto:
        apellidos, _, pila = texto.partition(",")
        texto = f"{pila.strip()} {apellidos.strip()}".strip()
    partes = []
    for palabra in texto.split():
        if palabra.isupper() or palabra.islower():
            minusculas = palabra.lower()
            partes.append(minusculas if minusculas in {"de", "del", "la", "las", "los", "y"} else minusculas.capitalize())
        else:
            partes.append(palabra)
    return " ".join(partes)


def _palabras(nombre):
    crudo = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode("ascii")
    return {p for p in re.split(r"[^a-zA-Z0-9]+", crudo.lower()) if len(p) > 1}


def emparejar(jugadores, filas):
    """
    Empareja jugadores de la ficha con filas de Universo.

    En la ficha el club los tiene por el nombre corto ("Eloy") y Universo los manda por su
    licencia ("BUSTAMANTE SALADO, ELOY"), así que además del nombre completo se acepta que el
    nombre de la ficha esté CONTENIDO en el de Universo. Si dos jugadores de Universo encajan
    con el mismo (dos "Sergio"), no se toca a ninguno: se devuelve suelto para que lo mire el
    club. Devuelve (parejas, jugadores_sueltos, filas_sueltas).
    """
    filas = [f for f in (filas or []) if isinstance(f, dict)]
    parejas = []
    usados = set()
    casadas = set()

    por_nombre = {}
    for jugador in jugadores:
        for candidato in (getattr(jugador, "full_name", ""), getattr(jugador, "name", "")):
            clave = _clave(candidato)
            if clave:
                por_nombre.setdefault(clave, jugador)

    # 1) Nombre completo, aunque venga en otro orden.
    for indice, fila in enumerate(filas):
        jugador = por_nombre.get(_clave(fila.get("name")))
        if jugador is not None and jugador.id not in usados:
            usados.add(jugador.id)
            casadas.add(indice)
            parejas.append((jugador, fila))

    # 2) El nombre de la ficha contenido en el de Universo, y sólo si no hay dudas.
    for jugador in jugadores:
        if jugador.id in usados:
            continue
        suyas = _palabras(getattr(jugador, "full_name", "")) or _palabras(getattr(jugador, "name", ""))
        if not suyas:
            continue
        candidatos = [
            i for i, fila in enumerate(filas)
            if i not in casadas and suyas and suyas <= _palabras(fila.get("name"))
        ]
        if len(candidatos) == 1:
            usados.add(jugador.id)
            casadas.add(candidatos[0])
            parejas.append((jugador, filas[candidatos[0]]))

    # 3) Último recurso: el dorsal, que dentro de la temporada es estable.
    for indice, fila in enumerate(filas):
        if indice in casadas:
            continue
        dorsal = fila.get("dorsal")
        if not dorsal:
            continue
        jugador = next(
            (j for j in jugadores if j.id not in usados and str(getattr(j, "number", "") or "") == str(dorsal)),
            None,
        )
        if jugador is not None:
            usados.add(jugador.id)
            casadas.add(indice)
            parejas.append((jugador, fila))

    sueltos = [j for j in jugadores if j.id not in usados]
    sueltas = [
        _texto(fila.get("name")) or "(sin nombre)" for i, fila in enumerate(filas) if i not in casadas
    ]
    return parejas, sueltos, sueltas


def descargar_foto(url, timeout=20):
    """Baja la foto. Devuelve bytes o '' (nunca revienta el import por una foto)."""
    import requests

    try:
        respuesta = requests.get(url, timeout=timeout)
        respuesta.raise_for_status()
        contenido = respuesta.content or b""
    except Exception:
        logger.warning("No se pudo bajar la foto de Universo: %s", url)
        return b""
    if len(contenido) < 800:
        # Universo devuelve un png de 1px cuando el jugador no tiene foto.
        return b""
    return contenido


def _guardar_foto_del_jugador(player, contenido):
    from django.core.files.base import ContentFile

    from .views import save_player_photo

    return save_player_photo(player, ContentFile(contenido, name=f"universo-{player.id}.jpg"))


def aplicar_plantilla(team, filas, *, sobrescribir=False, bajar_fotos=True, descargar=None, guardar_foto=None):
    """
    Completa los jugadores del equipo con lo que trae Universo.

    Por defecto sólo rellena huecos: si el club ya puso dorsal o posición, manda el club.
    NO crea jugadores: los que Universo trae y no están en la ficha se devuelven por nombre.
    """
    from .models import Player

    descargar = descargar or descargar_foto
    guardar_foto = guardar_foto or _guardar_foto_del_jugador

    jugadores = list(Player.objects.filter(team=team, is_active=True))
    parejas, sueltos, sueltas = emparejar(jugadores, filas or [])

    resumen = {
        "actualizados": [],
        "sin_cambios": [],
        "no_estan_en_universo": [j.name for j in sueltos],
        "no_estan_en_la_ficha": sueltas,
        "fotos": [],
    }
    for jugador, fila in parejas:
        fila = fila or {}
        raw = fila.get("raw") if isinstance(fila.get("raw"), dict) else {}
        cambios = []

        dorsal = fila.get("dorsal")
        if dorsal and (sobrescribir or not getattr(jugador, "number", None)):
            if int(dorsal) != (jugador.number or 0):
                jugador.number = int(dorsal)
                cambios.append("number")

        completo = nombre_persona(fila.get("name"))
        if completo and (sobrescribir or not _texto(getattr(jugador, "full_name", ""))):
            jugador.full_name = completo[:180]
            cambios.append("full_name")

        posicion = _texto(fila.get("position"))
        if posicion and (sobrescribir or not _texto(getattr(jugador, "position", ""))):
            jugador.position = posicion[:60]
            cambios.append("position")

        nacimiento = leer_fecha(_buscar(raw, CLAVES_NACIMIENTO))
        if nacimiento and (sobrescribir or not getattr(jugador, "birth_date", None)):
            jugador.birth_date = nacimiento
            cambios.append("birth_date")

        licencia = _texto(raw.get("cod_licencia"))
        if licencia and hasattr(jugador, "federation_license_number"):
            if sobrescribir or not _texto(getattr(jugador, "federation_license_number", "")):
                jugador.federation_license_number = licencia[:80]
                cambios.append("federation_license_number")

        pais = _buscar(raw, CLAVES_NACIONALIDAD)
        if pais and hasattr(jugador, "nationality") and (sobrescribir or not _texto(getattr(jugador, "nationality", ""))):
            jugador.nationality = pais[:60]
            cambios.append("nationality")

        if cambios:
            jugador.save(update_fields=cambios)
            resumen["actualizados"].append(f"{jugador.name}: " + ", ".join(cambios))
        else:
            resumen["sin_cambios"].append(jugador.name)

        if bajar_fotos:
            foto = url_de_foto(_buscar(raw, CLAVES_FOTO))
            if foto and (sobrescribir or not getattr(jugador, "photo_updated_at", None)):
                contenido = descargar(foto)
                if contenido and guardar_foto(jugador, contenido):
                    resumen["fotos"].append(jugador.name)
    return resumen


def importar_plantilla_de_universo(team, *, sobrescribir=False, fetch=None, codigo="", **extra):
    """
    Trae la plantilla de Universo y la aplica. `fetch` se inyecta para poder probarlo.

    `codigo` permite pedir OTRO equipo de origen: los jugadores que suben de categoría están
    en la plantilla del equipo del año pasado (el infantil), no en la del cadete.
    """
    codigo = str(codigo or "").strip() or str(getattr(team, "external_id", "") or "").strip()
    if not codigo:
        raise ValueError(
            "Este equipo no tiene código de Universo. Pega la URL de su ficha en Configuración → Competición."
        )
    if fetch is None:
        from .universo_client import fetch_universo_team_roster

        fetch = fetch_universo_team_roster
    filas = fetch(codigo) or []
    resumen = aplicar_plantilla(team, filas, sobrescribir=sobrescribir, **extra)
    resumen["filas_universo"] = len(filas)
    return resumen
