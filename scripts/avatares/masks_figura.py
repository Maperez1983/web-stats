"""
Máscaras de pelo y de piel de una figura base, deducidas de la propia imagen.

El generador de avatares necesita, por cada cuerpo, dos máscaras: dónde está el pelo (para
teñirlo del color del jugador) y dónde está la piel (para el grado de piel cuando no hay foto).
Las del adulto se hicieron a mano; a mano por cada figura de niño son horas de recorte, así que
aquí se deducen: la cara la encuentra insightface, y a partir de ella se sabe dónde mirar.

    python masks_figura.py <figura.png> <clave>     # escribe masks/hair_<clave>.png y skin_<clave>.png
    python masks_figura.py --comparar               # se mide contra las máscaras del adulto

Uso previsto: una vez por figura nueva, mirando el resultado. No es magia, es una heurística.
"""
import sys
import os

import numpy as np
from PIL import Image, ImageFilter
from insightface.app import FaceAnalysis

REPO = os.environ.get("WEBSTATS_REPO") or "/Volumes/Mac Satecchi/Mac/Web-stats-analysis-entry-clean"
ASSETS = os.path.join(REPO, "football/static/football/images/coach_roster_avatars")

_app = None


def _cara(bgr):
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=-1, det_size=(640, 640))
    caras = _app.get(bgr)
    if not caras:
        raise SystemExit("No se detecta cara en la figura.")
    return sorted(caras, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]


def _dist_piel(rgb, muestra):
    """Distancia al tono de piel muestreado, en YCrCb (la crominancia aguanta la luz mejor que RGB)."""
    def ycrcb(a):
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        y = 0.299 * r + 0.587 * g + 0.114 * b
        return np.stack([y, (r - y) * 0.713 + 128, (b - y) * 0.564 + 128], axis=-1)
    a = ycrcb(rgb.astype(np.float32))
    m = ycrcb(muestra.astype(np.float32).reshape(1, 1, 3))[0, 0]
    # La luminancia pesa poco: un brazo a la sombra sigue siendo piel.
    d = np.sqrt(((a[..., 1] - m[1]) ** 2 + (a[..., 2] - m[2]) ** 2) + 0.08 * (a[..., 0] - m[0]) ** 2)
    return d


def construir(path_figura):
    im = Image.open(path_figura).convert("RGBA")
    rgba = np.asarray(im)
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3]
    dentro = alpha > 128

    cara = _cara(rgb[:, :, ::-1].astype(np.uint8).copy())
    x0, y0, x1, y1 = [float(v) for v in cara.bbox]
    ancho, alto = x1 - x0, y1 - y0
    kps = cara.kps  # ojo izq, ojo der, nariz, boca izq, boca der
    ojo_y = float((kps[0][1] + kps[1][1]) / 2)
    nariz = kps[2]

    # Tono de piel: la mejilla, no la frente (la frente suele tener brillo y flequillo).
    r = max(3, int(ancho * 0.06))
    cx, cy = int(nariz[0]), int(nariz[1])
    muestra = np.median(rgb[cy - r:cy + r, cx - r:cx + r].reshape(-1, 3), axis=0)

    d = _dist_piel(rgb, muestra)
    piel = dentro & (d < 26)

    # La CABEZA: una elipse generosa alrededor de la cara. Fuera de ahí no hay pelo que valga.
    yy, xx = np.mgrid[0:rgba.shape[0], 0:rgba.shape[1]]
    ccx, ccy = (x0 + x1) / 2, y0 + alto * 0.35
    cabeza = (((xx - ccx) / (ancho * 0.95)) ** 2 + ((yy - ccy) / (alto * 0.95)) ** 2) < 1.0

    # PELO = dentro de la cabeza, por encima de los ojos (con margen para las patillas), dentro de
    # la silueta y que no sea piel. El corte por los ojos evita que la sombra de la mandibula y el
    # cuello entren como si fueran pelo.
    pelo = cabeza & dentro & (~piel) & (yy < ojo_y - alto * 0.02)
    # Los ojos y las cejas no son piel y caen dentro de la cabeza, asi que entraban en el pelo: al
    # tenirlo se le pintaban los ojos del color del pelo. Se recortan a mano.
    for ojo in (kps[0], kps[1]):
        r_ojo = ancho * 0.22
        pelo &= ~((((xx - float(ojo[0])) / r_ojo) ** 2 + ((yy - float(ojo[1])) / (r_ojo * 0.8)) ** 2) < 1.0)

    # PIEL = la piel de verdad de todo el cuerpo (cara, brazos, piernas), quitando el pelo.
    piel = piel & (~pelo)

    def limpiar(m, blur=2.5):
        img = Image.fromarray((m * 255).astype("uint8"), "L")
        img = img.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(blur))
        return img

    return limpiar(pelo), limpiar(piel)


def _solape(a, b):
    """Cuánto se parecen dos máscaras (Jaccard sobre el 50%)."""
    a = np.asarray(a.convert("L")) > 127
    b = np.asarray(b.convert("L")) > 127
    u = (a | b).sum()
    return float((a & b).sum()) / u if u else 0.0


if __name__ == "__main__":
    if "--comparar" in sys.argv:
        pelo, piel = construir(os.path.join(ASSETS, "library/kit_home_hd.png"))
        for nombre, hecho, mano in (
            ("pelo", pelo, Image.open(os.path.join(ASSETS, "masks/hair_home.png"))),
            ("piel", piel, Image.open(os.path.join(ASSETS, "masks/skin_home.png"))),
        ):
            print(f"{nombre}: solape con la máscara hecha a mano = {_solape(hecho, mano):.2f}")
            hecho.save(f"/tmp/auto_{nombre}_adulto.png")
        print("Escritas /tmp/auto_pelo_adulto.png y /tmp/auto_piel_adulto.png para mirarlas.")
        raise SystemExit(0)

    figura, clave = sys.argv[1], sys.argv[2]
    pelo, piel = construir(figura)
    pelo.save(os.path.join(ASSETS, f"masks/hair_{clave}.png"))
    piel.save(os.path.join(ASSETS, f"masks/skin_{clave}.png"))
    print(f"OK masks/hair_{clave}.png y masks/skin_{clave}.png")
