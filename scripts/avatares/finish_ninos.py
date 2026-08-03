"""
Deja las figuras de niño listas para el generador de avatares.

Lo que hace, por figura: recorta el fondo, la encaja en el mismo lienzo que la figura de adulto
(651x1482, los pies abajo) y le pega el escudo del club y el patrocinador REALES encima de los que
Flux se inventa.

La diferencia con finish_kits.py (que hizo las equipaciones de adulto) es dónde van esos logos: allí
estaban en porcentajes fijos del lienzo, y eso sólo vale si todos los cuerpos tienen las mismas
proporciones. Un niño tiene la cabeza mucho más grande respecto al tronco, así que el escudo
acabaría en la barriga. Aquí se colocan respecto a la CARA, que es lo que sí se puede medir.

    python finish_ninos.py            # todas las de ~/ai-image-gen/ninos/raw_*.png
"""
import glob
import os
import re

import numpy as np
from PIL import Image
from rembg import remove
from insightface.app import FaceAnalysis

REPO = os.environ.get("WEBSTATS_REPO") or "/Volumes/Mac Satecchi/Mac/Web-stats-analysis-entry-clean"
LOGOS = os.path.join(REPO, "football/static/football/images/kit_logos/")
DESTINO = os.path.join(REPO, "football/static/football/images/coach_roster_avatars/library")
ORIGEN = os.path.expanduser("~/ai-image-gen/ninos")
CW, CH = 651, 1482          # el lienzo de la figura de adulto: todas tienen que medir igual

_app = None


def cara_de(rgba):
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=-1, det_size=(640, 640))
    bgr = np.asarray(rgba)[:, :, :3][:, :, ::-1].copy()
    caras = _app.get(bgr)
    if not caras:
        return None
    return sorted(caras, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]


def _sponsor(claro=False):
    """
    El logo del patrocinador. Gris muy oscuro sobre la equipacion (fondo blanco y verde) y BLANCO
    sobre el chandal: en negro sobre negro no se veia, que es como salio la primera tanda.
    """
    mo = Image.open(os.path.expanduser("~/ai-image-gen/modernia_logo.png")).convert("RGBA")
    mo = mo.crop(mo.split()[3].getbbox())
    tinta = (255, 255, 255) if claro else (15, 15, 15)
    px = mo.load()
    for y in range(mo.size[1]):
        for x in range(mo.size[0]):
            px[x, y] = (*tinta, px[x, y][3])
    return mo


def ancho(im, w):
    return im.resize((w, max(1, int(w * im.size[1] / im.size[0]))))


# El verde de la equipacion APROBADA, medido en la figura de adulto (kit_home_hd.png). Flux se
# inventa un verde distinto en cada tirada -salieron siete- y eso rompe justo lo que se buscaba:
# que todos lleven la misma camiseta. Aqui se les pone el verde bueno.
VERDE_CLUB = (3, 89, 51)


def unificar_verde(im, objetivo=VERDE_CLUB):
    """
    Lleva el verde de la equipacion al verde del club, conservando pliegues y sombras.

    Se cambia el TONO y la saturacion, no la luminosidad: si se pintara plano, la camiseta
    quedaria como una mancha recortada. Las rayas blancas no se tocan (no son verde).
    """
    import colorsys

    a = np.asarray(im).astype(np.float32)
    rgb, alfa = a[:, :, :3], a[:, :, 3]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    # "Verde de tela": el verde manda con claridad sobre rojo y azul. Deja fuera piel, blanco,
    # botas y el fondo transparente.
    mascara = (alfa > 128) & (g > r + 25) & (g > b + 25)
    if mascara.sum() < 500:
        return im

    h_obj, l_obj, s_obj = colorsys.rgb_to_hls(*[c / 255.0 for c in objetivo])
    maxc = rgb.max(axis=2) / 255.0
    minc = rgb.min(axis=2) / 255.0
    lum = (maxc + minc) / 2.0
    # La luminosidad se reescala para que la MEDIA case con la del verde bueno: si no, un verde
    # menta clarito seguiria pareciendo menta aunque el tono fuera el correcto.
    lum_media = float(np.median(lum[mascara]))
    ajuste = (l_obj / lum_media) if lum_media > 0.01 else 1.0
    lum_nueva = np.clip(lum * ajuste, 0.04, 0.96)

    ys, xs = np.nonzero(mascara)
    salida = rgb.copy()
    for y, x in zip(ys, xs):
        rr, gg, bb = colorsys.hls_to_rgb(h_obj, float(lum_nueva[y, x]), s_obj)
        salida[y, x] = (rr * 255.0, gg * 255.0, bb * 255.0)
    a[:, :, :3] = salida
    return Image.fromarray(a.astype("uint8"), "RGBA")


def finish(origen, destino):
    # El chandal es negro: el patrocinador tiene que ir en blanco o desaparece.
    chandal = "chandal" in os.path.basename(destino)
    fig = remove(Image.open(origen).convert("RGBA"))
    fig = fig.crop(fig.split()[3].getbbox())
    s = (CH * 0.99) / fig.size[1]
    if fig.size[0] * s > CW:
        s = (CW * 0.98) / fig.size[0]
    fig = fig.resize((int(fig.size[0] * s), int(fig.size[1] * s)))
    fig = unificar_verde(fig)   # ANTES de los logos: el escudo tambien tiene verde y no se toca
    lienzo = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    lienzo.alpha_composite(fig, ((CW - fig.size[0]) // 2, CH - fig.size[1] - int(CH * 0.005)))

    cara = cara_de(lienzo)
    if cara is None:
        print(f"AVISO {os.path.basename(destino)}: sin cara detectada, no se pegan los logos")
        lienzo.save(destino)
        return
    x0, y0, x1, y1 = [float(v) for v in cara.bbox]
    fw, fh = x1 - x0, y1 - y0
    centro = (x0 + x1) / 2
    barbilla = y1

    crest = Image.open(LOGOS + "benagalbon_crest_alpha.png").convert("RGBA")
    nike = Image.open(LOGOS + "nike_swoosh.png").convert("RGBA")
    mo = _sponsor(claro=chandal)

    # Escudo: pecho derecho (a su izquierda), por debajo del cuello. Las distancias van en
    # "caras": es la unica medida que se mantiene entre un benjamin y un cadete.
    c = ancho(crest, max(24, int(fw * 0.70)))
    lienzo.alpha_composite(c, (int(centro + fw * 0.22), int(barbilla + fh * 0.80)))
    # Marca: pecho izquierdo, a la misma altura.
    n = ancho(nike, max(18, int(fw * 0.50)))
    lienzo.alpha_composite(n, (int(centro - fw * 0.72), int(barbilla + fh * 0.88)))
    # Patrocinador: centrado, en el pecho bajo.
    m = ancho(mo, max(60, int(fw * 2.0)))
    lienzo.alpha_composite(m, (int(centro - m.size[0] / 2), int(barbilla + fh * 1.85)))

    lienzo.save(destino)
    print("OK", os.path.basename(destino))


if __name__ == "__main__":
    for origen in sorted(glob.glob(os.path.join(ORIGEN, "raw_*.png"))):
        clave = re.sub(r"^raw_", "", os.path.basename(origen)).replace(".png", "")
        # Los chandales son figuras de ESTADO (a prueba / sin ficha): se sirven tal cual, sin
        # mascaras y sin pasar por el generador, asi que conservan el nombre que espera la app.
        destino = f"{clave}.png" if clave.startswith("chandal_") else f"nino_{clave}_hd.png"
        finish(origen, os.path.join(DESTINO, destino))
