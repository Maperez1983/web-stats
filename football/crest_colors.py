"""Colores de equipacion a partir del escudo del club.

Sirve para PRECARGAR la equipacion de un rival: el entrenador confirma o corrige,
pero no parte de cero con 56 fichas vacias.

No es adivinar: en futbol modesto el escudo es la camiseta. El problema son los
escudos ILUSTRADOS -paisajes, cielos, balones-, donde el color mas repetido puede
ser el azul del cielo. Por eso:

  - Se mira sobre todo la CORONA del escudo (el borde), que es donde vive el color
    heraldico; el centro suele ser el dibujo.
  - Se descartan blancos, negros y grises: son contorno y letras, no equipacion.
  - Se devuelven varios candidatos, no uno: la pantalla los ensenia y se elige.
"""
import io

import numpy as np
from PIL import Image

# Un color se considera "de equipacion" si tiene color de verdad y no es ni
# demasiado oscuro (contorno) ni casi blanco (fondo del escudo).
SAT_MINIMA = 0.22
VALOR_MINIMO = 45
BLANCO = 238


def _mascara_util(rgb, alfa):
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    casi_blanco = (rgb[:, :, 0] > BLANCO) & (rgb[:, :, 1] > BLANCO) & (rgb[:, :, 2] > BLANCO)
    return (alfa > 200) & (sat > SAT_MINIMA) & (mx > VALOR_MINIMO) & ~casi_blanco


def _agrupa(pixeles, cuantos):
    if len(pixeles) < 30:
        return []
    claves = (pixeles >> 5).astype(np.int32)
    planas = claves[:, 0] * 1024 + claves[:, 1] * 32 + claves[:, 2]
    unicos, cuentas = np.unique(planas, return_counts=True)
    orden = np.argsort(-cuentas)[:cuantos]
    salida = []
    for i in orden:
        sel = planas == unicos[i]
        medio = pixeles[sel].mean(axis=0).astype(int)
        salida.append(("#%02x%02x%02x" % tuple(medio), round(100.0 * cuentas[i] / len(pixeles))))
    return salida


def colores_de_escudo(datos, cuantos=3):
    """[(hex, % de la tela del escudo)] ordenados por presencia.

    Pesa doble el borde del escudo, que es donde esta el color del club y no el
    dibujo del centro.
    """
    try:
        im = Image.open(io.BytesIO(datos)).convert("RGBA")
    except Exception:
        return []
    a = np.array(im)
    rgb = a[:, :, :3].astype(int)
    util = _mascara_util(rgb, a[:, :, 3])
    if not util.any():
        return []
    alto, ancho = util.shape
    borde = np.zeros_like(util)
    m = max(2, int(min(alto, ancho) * 0.18))
    borde[:m, :] = True
    borde[-m:, :] = True
    borde[:, :m] = True
    borde[:, -m:] = True
    pixeles = np.concatenate([rgb[util], rgb[util & borde]]) if (util & borde).any() else rgb[util]
    return _agrupa(pixeles, cuantos)


def _acromaticos(datos):
    """Cuanto negro y cuanto blanco hay en el escudo, en tanto por ciento.

    Se miran aparte porque para el color PRINCIPAL estorban -son contorno y
    letras- pero para el RIBETE son de lo mas comun: media liga juega de
    negro o blanco con otro color. Descartarlos del todo hacia que a un club
    negro y amarillo se le propusiera amarillo con ribete blanco.
    """
    try:
        im = Image.open(io.BytesIO(datos)).convert("RGBA")
    except Exception:
        return 0.0, 0.0
    a = np.array(im)
    rgb = a[:, :, :3].astype(int)
    dentro = a[:, :, 3] > 200
    if not dentro.any():
        return 0.0, 0.0
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    gris = (mx - mn) < 30
    negro = dentro & gris & (mx < 70)
    blanco = dentro & gris & (mn > 205)
    total = int(dentro.sum())
    return 100.0 * int(negro.sum()) / total, 100.0 * int(blanco.sum()) / total


def equipacion_propuesta(datos):
    """{'home_main', 'home_trim', 'candidatos'} listo para precargar el formulario."""
    candidatos = colores_de_escudo(datos, cuantos=3)
    if not candidatos:
        return {}
    principal = candidatos[0][0]
    p = np.array([int(principal[i:i + 2], 16) for i in (1, 3, 5)])
    ribete = ""
    # El ribete: el siguiente candidato que NO sea casi el mismo color.
    for hexa, _ in candidatos[1:]:
        c = np.array([int(hexa[i:i + 2], 16) for i in (1, 3, 5)])
        if np.abs(c - p).sum() > 90:
            ribete = hexa
            break
    # Si el escudo tiene mucho negro o mucho blanco, gana como ribete: es lo que
    # de verdad lleva la camiseta.
    pct_negro, pct_blanco = _acromaticos(datos)
    if pct_negro >= 12 and pct_negro >= pct_blanco:
        ribete = "#111418"
    elif pct_blanco >= 18:
        ribete = "#ffffff"
    return {
        "home_main": principal,
        "home_trim": ribete or "#ffffff",
        "candidatos": candidatos,
        "negro_pct": round(pct_negro),
        "blanco_pct": round(pct_blanco),
    }
