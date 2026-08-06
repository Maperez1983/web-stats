"""Precarga la equipacion de los rivales a partir de su escudo.

Dos cosas que hoy no hacia nadie:

1. GUARDAR el escudo. Hasta ahora cada rival tenia solo la URL en laPreferente y
   la pantalla la enlazaba. Si esa web cambia una ruta, el club se queda sin los
   56 escudos de golpe. Se descargan una vez y se quedan en MEDIA.
2. PRECARGAR sus colores en kit_theme:v1, que ya admite ajustes por equipo pero
   solo se escribia para el equipo propio.

El color se PROPONE, no se impone: se escribe solo si ese equipo no tiene nada
guardado, para no pisar lo que el entrenador haya corregido a mano.
"""
import logging

from django.core.files.base import ContentFile

log = logging.getLogger(__name__)

MAX_ESCUDO = 3 * 1024 * 1024
TIEMPO_LIMITE = 12


def _url_grande(url):
    """laPreferente sirve miniaturas en /thumbs/. La grande es la misma sin eso.

    Importa: la miniatura son unos 100 px y para la chapa de 360 se queda corta.
    """
    texto = str(url or "").strip()
    if not texto:
        return ""
    if texto.startswith("//"):
        texto = "https:" + texto
    elif texto.startswith("www."):
        texto = "https://" + texto
    return texto.replace("/thumbs/", "/")


def descargar_escudo(team, *, guardar=True, limite=None, url_escudo=""):
    """Devuelve los bytes del escudo del equipo, y los guarda en crest_image.

    `limite` acorta la espera: al pintar una pantalla no se puede tener al usuario
    12 segundos esperando a que responda una web de terceros. En segundo plano si.
    """
    try:
        if getattr(team, "crest_image", None):
            team.crest_image.open("rb")
            datos = team.crest_image.read()
            team.crest_image.close()
            if datos:
                return datos
    except Exception:
        pass
    # El escudo del rival NO suele estar en el equipo: la pantalla lo resuelve
    # desde el Universo y lo pinta directamente. Por eso se admite recibirlo:
    # buscarlo solo en team.crest_url daba "sin escudo" para todos.
    url = _url_grande(url_escudo or getattr(team, "crest_url", ""))
    if not url:
        return b""
    try:
        import requests

        resp = requests.get(url, timeout=(limite or TIEMPO_LIMITE), headers={"User-Agent": "SegundaJugada/1.0"})
        if resp.status_code != 200:
            return b""
        datos = resp.content or b""
    except Exception as exc:
        log.info("escudo no descargado (%s): %s", url, exc)
        return b""
    if not datos or len(datos) > MAX_ESCUDO:
        return b""
    if guardar:
        try:
            nombre = f"{getattr(team, 'slug', '') or team.id}-escudo.png"
            team.crest_image.save(nombre, ContentFile(datos), save=True)
        except Exception as exc:
            log.info("escudo no guardado (%s): %s", team, exc)
    return datos


def precargar_equipacion(workspace, team, *, forzar=False, url_escudo=""):
    """Propone la equipacion del rival y la guarda si ese equipo no tenia nada.

    Escribe en la preferencia `rival_kit2d:<id>`, que es la que lee y guarda el
    formulario de la ficha del rival. (El primer intento la escribia en
    kit_theme:v1 -donde viven los colores del equipo PROPIO- y por ahi no la leia
    nadie: se veia guardado y la ficha seguia en verde.)

    Devuelve un dict con lo que ha hecho, para poder contarlo por pantalla.
    """
    from .crest_colors import equipacion_propuesta
    from .models import WorkspacePreference

    salida = {"equipo": str(getattr(team, "name", "") or team), "estado": "sin escudo"}
    try:
        clave_pref = "rival_kit2d:%d" % int(getattr(team, "id", 0) or 0)
    except Exception:
        salida["estado"] = "equipo sin id"
        return salida

    pref = WorkspacePreference.objects.filter(workspace=workspace, key=clave_pref).first()
    valor = dict(pref.value) if pref and isinstance(pref.value, dict) else {}
    ya_tiene = any(valor.get(f"{s}_main_color") or valor.get(f"{s}_trim_color")
                   for s in ("home", "away", "third", "gk", "gk2", "gk3"))
    if ya_tiene and not forzar:
        salida["estado"] = "ya tenia colores"
        return salida

    datos = descargar_escudo(team, url_escudo=url_escudo)
    if not datos:
        return salida
    propuesta = equipacion_propuesta(datos)
    if not propuesta:
        salida["estado"] = "el escudo no da color util"
        return salida

    principal = propuesta["home_main"]
    ribete = propuesta["home_trim"]
    valor.update({
        "home_main_color": principal,
        "home_trim_color": ribete,
        # La 2a invertida, que es lo que hace cualquier equipo. La 3a y las de
        # portero no salen del escudo: se dejan para que las ponga el entrenador.
        "away_main_color": ribete,
        "away_trim_color": principal,
        "origen": "escudo",
    })
    WorkspacePreference.objects.update_or_create(
        workspace=workspace, key=clave_pref, defaults={"value": valor}
    )
    salida.update({
        "estado": "precargado",
        "principal": principal,
        "ribete": ribete,
        "candidatos": propuesta.get("candidatos", []),
    })
    return salida


def precargar_equipaciones(workspace, equipos, *, forzar=False, escudos=None):
    """Pasa por todos los rivales. Devuelve (resumen, detalle).

    `escudos` es {id_equipo: url}, porque la URL del escudo la resuelve la pantalla
    y no esta guardada en el equipo.
    """
    escudos = escudos or {}
    detalle = []
    for team in equipos or []:
        try:
            url = escudos.get(int(getattr(team, "id", 0) or 0), "")
            detalle.append(precargar_equipacion(workspace, team, forzar=forzar, url_escudo=url))
        except Exception as exc:
            log.info("precarga fallida (%s): %s", team, exc)
            detalle.append({"equipo": str(team), "estado": "error"})
    resumen = {}
    for fila in detalle:
        resumen[fila["estado"]] = resumen.get(fila["estado"], 0) + 1
    return resumen, detalle
