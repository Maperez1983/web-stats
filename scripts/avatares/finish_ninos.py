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


def _sponsor():
    """El logo del patrocinador, en gris muy oscuro (como en las equipaciones de adulto)."""
    mo = Image.open(os.path.expanduser("~/ai-image-gen/modernia_logo.png")).convert("RGBA")
    mo = mo.crop(mo.split()[3].getbbox())
    px = mo.load()
    for y in range(mo.size[1]):
        for x in range(mo.size[0]):
            px[x, y] = (15, 15, 15, px[x, y][3])
    return mo


def ancho(im, w):
    return im.resize((w, max(1, int(w * im.size[1] / im.size[0]))))


def finish(origen, destino):
    fig = remove(Image.open(origen).convert("RGBA"))
    fig = fig.crop(fig.split()[3].getbbox())
    s = (CH * 0.99) / fig.size[1]
    if fig.size[0] * s > CW:
        s = (CW * 0.98) / fig.size[0]
    fig = fig.resize((int(fig.size[0] * s), int(fig.size[1] * s)))
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
    mo = _sponsor()

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
        finish(origen, os.path.join(DESTINO, f"nino_{clave}_hd.png"))
