"""
Cómo se escribe el nombre de un club.

Los equipos entran de tres sitios —la federación, el importador y el alta a mano— y cada uno
escribe distinto: "ALHAURIN DE LA TORRE C.F.", "ALHAURÍN DE LA TORRE CF", "CD LA CALA" y
"LA CALA C.D." son cuatro formas de dos clubes. En la aplicación deben leerse igual.

Lo que se cambia es SÓLO la forma: mayúsculas, tildes que ya vengan puestas y espacios. No se
tocan las palabras, ni se añaden ni se quitan siglas. Esto importa porque `name_key` -la clave
con la que la clasificación empareja cada fila de la tabla con su equipo- se calcula quitando
acentos, puntuación y mayúsculas: mientras las PALABRAS no cambien, la clave no cambia y no se
rompe ningún emparejado.
"""

from __future__ import annotations

import re


# Se escriben enteras en mayúscula: son siglas, no palabras.
SIGLAS = {
    "cd", "cf", "ud", "ad", "sad", "fc", "ef", "cdf", "sd", "rcd", "cp", "pd", "ucd",
    "af", "at", "ca", "ef", "emf", "amf",
}

# Preposiciones y conjunciones: en minúscula salvo al principio.
PARTICULAS = {"de", "del", "y", "e", "da", "do"}

# Los artículos dependen de lo que llevan DELANTE: en "Alhaurín de la Torre" es partícula,
# pero en "La Cala", "El Palo" o "El Ejido" abre el topónimo y va en mayúscula.
ARTICULOS = {"la", "las", "los", "el"}


def _palabra(bruta, *, primera, anterior=""):
    """Formatea UNA palabra respetando puntos de sigla ('C.D.') y guiones ('Caro-Accino')."""
    if not bruta:
        return bruta

    solo_letras = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", bruta).lower()

    # Sigla: la conocemos ("cd", "sad") o lleva puntos DENTRO ("C.D.", "G.I."). Un punto sólo
    # al final no la hace sigla, la hace abreviatura de una palabra: "STA." es Santa y "PTO."
    # es Puerto, así que van como "Sta." y "Pto.", no gritando.
    if solo_letras in SIGLAS:
        return bruta.upper()
    if "." in bruta[:-1]:
        return bruta.upper()

    if solo_letras in PARTICULAS and not primera:
        return bruta.lower()
    if solo_letras in ARTICULOS and not primera and anterior in PARTICULAS:
        return bruta.lower()

    if "-" in bruta:
        return "-".join(_palabra(trozo, primera=True) for trozo in bruta.split("-"))

    # Capitaliza respetando lo que ya esté bien escrito ("McCarthy" no se toca si trae mezcla).
    minuscula = bruta.lower()
    for indice, caracter in enumerate(minuscula):
        if caracter.isalpha():
            return minuscula[:indice] + caracter.upper() + minuscula[indice + 1:]
    return bruta


def formato_nombre_club(nombre):
    """
    Nombre de club legible: "ALHAURIN DE LA TORRE C.F." → "Alhaurin de la Torre C.F.".

    Sólo se toca lo que VIENE GRITANDO. Si un nombre ya está escrito con mayúsculas y
    minúsculas, se deja tal cual: "Mijas Las Lagunas B" tiene un "Las" que es topónimo, no
    partícula, y bajarlo a minúscula lo estropea. Distinguirlos no se puede por regla, así que
    manda quien lo escribió.

    Y no se inventan tildes: poner "Alhaurín" donde la federación escribió "ALHAURIN" sería
    cambiar el dato, no su formato. Eso se corrige a mano, club por club.
    """
    limpio = re.sub(r"\s+", " ", str(nombre or "").strip())
    if not limpio:
        return ""
    palabras = limpio.split(" ")
    # Una sola palabra en minúsculas ya basta para saber que alguien lo escribió a conciencia.
    grita = all(p.upper() == p for p in palabras)
    if not grita:
        return limpio
    salida = []
    for indice, palabra in enumerate(palabras):
        anterior = re.sub(r"[^a-záéíóúüñ]", "", palabras[indice - 1].lower()) if indice else ""
        salida.append(_palabra(palabra, primera=(indice == 0), anterior=anterior))
    return " ".join(salida)


def revisar(objetos):
    """(objeto, nombre_actual, nombre_nuevo) de lo que cambiaría. No toca nada."""
    cambios = []
    for objeto in objetos:
        actual = str(getattr(objeto, "name", "") or "")
        nuevo = formato_nombre_club(actual)
        if nuevo and nuevo != actual:
            cambios.append((objeto, actual, nuevo))
    return cambios


def aplicar(objetos):
    """
    Escribe el formato nuevo. Devuelve un resumen legible.

    Se comprueba SIEMPRE que la clave de emparejado no cambia; si cambiara, ese nombre se deja
    como está y se dice. Vale más un nombre feo que una clasificación que deja de casar.
    """
    from .models import normalize_team_name_key

    resumen = {"cambiados": [], "rechazados": []}
    for objeto, actual, nuevo in revisar(objetos):
        if normalize_team_name_key(actual) != normalize_team_name_key(nuevo):
            resumen["rechazados"].append(f"{actual} → {nuevo} (cambiaría su emparejado)")
            continue
        objeto.name = nuevo
        objeto.save(update_fields=["name"])
        resumen["cambiados"].append(f"{actual} → {nuevo}")
    return resumen
