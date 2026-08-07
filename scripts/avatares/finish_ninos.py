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


BLANCO_CLUB = (243, 243, 240)
BANDAS = 7          # rayas verticales a lo ancho del torso, empezando y acabando en verde


def _fila_entrepierna(dentro):
    """
    La fila donde se juntan las piernas. Por debajo hay dos tramos (una pierna y otra); por
    encima, uno solo. Es el limite anatomico de la camiseta: el pantalon empieza por encima, pero
    la camiseta NUNCA baja de ahi.
    """
    h = dentro.shape[0]
    for y in range(h - 5, int(h * 0.35), -1):
        fila = dentro[y].astype(np.int8)
        tramos = int(np.count_nonzero(np.diff(np.concatenate(([0], fila, [0]))) == 1))
        if tramos < 2:
            return y
    return int(h * 0.55)


def _mascara_piel(rgb, dentro, cara):
    """Piel del jugador, para no repintarle la cara ni los brazos. Muestrea su propio tono."""
    x0, y0, x1, y1 = [float(v) for v in cara.bbox]
    cx, cy = int((x0 + x1) / 2), int(y0 + (y1 - y0) * 0.62)
    rad = max(3, int((x1 - x0) * 0.08))
    muestra = np.median(rgb[cy - rad:cy + rad, cx - rad:cx + rad].reshape(-1, 3), axis=0)

    def ycrcb(v):
        r, g, b = v[..., 0], v[..., 1], v[..., 2]
        y = 0.299 * r + 0.587 * g + 0.114 * b
        return np.stack([y, (r - y) * 0.713 + 128, (b - y) * 0.564 + 128], axis=-1)

    a = ycrcb(rgb.astype(np.float32))
    m = ycrcb(muestra.astype(np.float32).reshape(1, 1, 3))[0, 0]
    d = np.sqrt((a[..., 1] - m[1]) ** 2 + (a[..., 2] - m[2]) ** 2)
    return dentro & (d < 30)


def uniformar_rayas(im, cara, verde=VERDE_CLUB, blanco=BLANCO_CLUB, bandas=BANDAS,
                    pantalon=None, rango_verde=(0.62, 1.30), rango_blanco=(0.88, 1.04),
                    umbral_oscuro=90):
    """
    Pinta LA MISMA camiseta en todas las figuras: mismo numero de rayas, mismos colores, y los
    pliegues de cada una respetados. Con `verde` y `blanco` iguales sale una equipacion lisa, que
    es como se fabrican la visitante, la turquesa y la blanca a partir de la titular.

    Igualar solo el color no bastaba: cada tirada de Flux dibujaba las rayas a su manera -unas
    anchas, otras finas, alguna con las mangas de otro color- y la equipacion tiene que ser LA del
    club, no un parecido.

    Se pinta SOLO la camiseta, y la camiseta se reconoce por una propiedad que no tiene ninguna
    otra prenda: es lo unico que lleva blanco. El pantalon y las medias son verde liso y las botas
    quedan por debajo; la piel se excluye aparte, muestreando su tono en la mejilla, porque si no
    al jugador se le pinta la cara.
    """
    a = np.asarray(im).astype(np.float32)
    rgb, alfa = a[:, :, :3], a[:, :, 3]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    dentro = alfa > 128
    piel = _mascara_piel(rgb, dentro, cara)
    es_verde = dentro & (~piel) & (g > r + 25) & (g > b + 25)
    es_blanco = dentro & (~piel) & (r > 165) & (g > 165) & (b > 165) & (abs(r - g) < 40) & (abs(g - b) < 40)
    tela = es_verde | es_blanco
    if tela.sum() < 2000:
        return im

    # Filas de camiseta: las que llevan blanco de forma apreciable, en el tercio alto del cuerpo.
    alto = a.shape[0]
    ancho_fila = tela.sum(axis=1).astype(np.float32)
    blanco_fila = es_blanco.sum(axis=1).astype(np.float32)
    con_blanco = (ancho_fila > 40) & (blanco_fila > ancho_fila * 0.12)
    barbilla = int(cara.bbox[3])
    con_blanco[:barbilla] = False
    con_blanco[int(alto * 0.72):] = False        # de la rodilla para abajo no hay camiseta
    # La camiseta no puede pasar de la entrepierna. Sin este tope, un pantalon palido con algo de
    # blanco se colaba como "fila de camiseta" y acababa con rayas pintadas.
    tope = _fila_entrepierna(dentro)
    con_blanco[tope:] = False
    filas = np.nonzero(con_blanco)[0]
    if len(filas) < 40:
        return im
    y_ini, y_fin = int(filas.min()), int(filas.max())

    yy, xx = np.mgrid[0:alto, 0:a.shape[1]]
    # La camiseta se RELLENA fila a fila, de un borde de tela al otro, en vez de ir pixel a pixel:
    # los pliegues mas oscuros no pasaban el filtro de "verde" y quedaban sin pintar, y la camiseta
    # salia moteada. Lo unico que se respeta dentro es la piel (cuello y brazos).
    camiseta = np.zeros_like(dentro)
    for y in range(y_ini, y_fin + 1):
        xs_fila = np.nonzero(tela[y])[0]
        if len(xs_fila) < 10:
            continue
        camiseta[y, xs_fila.min():xs_fila.max() + 1] = True
    camiseta &= dentro & (~piel)
    # CUELLO, HOMBROS Y MANGAS: son verde liso, sin una raya blanca, asi que su fila no pasaba el
    # filtro de "fila de camiseta" y se quedaban sin repintar. Sobre la titular no se notaba
    # -verde sobre verde-, pero al pasar a amarillo o turquesa quedaba un ribete verde alrededor
    # del cuello en casi todas las figuras. Se anexa cualquier verde que caiga entre la barbilla y
    # el bajo de la camiseta.
    camiseta |= (yy >= barbilla) & (yy <= y_fin) & es_verde & dentro & (~piel)
    # Lo que no es tela ni piel dentro de la camiseta es un logo (escudo, marca, patrocinador):
    # muy saturado o casi negro. Se protege, porque esta funcion tambien se usa sobre figuras que
    # YA los llevan pegados.
    maxc, minc = rgb.max(axis=2), rgb.min(axis=2)
    saturado = (maxc - minc) > 60
    # `umbral_oscuro` protege lo casi negro por considerarlo logo. Con 90 tambien se salvaban los
    # PLIEGUES mas hondos de la raya verde (llegan a 73 de maximo): al repintar de amarillo se
    # quedaban verdes y la camiseta seguia pareciendo rayada. Para una equipacion lisa se baja,
    # porque ahi cualquier verde que sobreviva canta; para la titular se deja como estaba.
    oscuro = maxc < umbral_oscuro
    camiseta &= ~((saturado & ~es_verde) | (oscuro & ~es_verde))
    if camiseta.sum() < 1500:
        return im

    # Ancho de banda medido en el TRAMO CENTRAL de una fila baja de la camiseta (sin mangas).
    y_ref = y_ini + int((y_fin - y_ini) * 0.8)
    xs = np.nonzero(camiseta[y_ref])[0]
    if len(xs) < 20:
        xs = np.nonzero(camiseta[y_fin - 2])[0]
    centro, ancho_torso = (xs.min() + xs.max()) / 2.0, float(xs.max() - xs.min() + 1)
    banda = max(6.0, ancho_torso / bandas)

    lum = rgb.max(axis=2) / 255.0
    ref_v = float(np.median(lum[es_verde & camiseta])) if (es_verde & camiseta).any() else 0.5
    ref_b = float(np.median(lum[es_blanco & camiseta])) if (es_blanco & camiseta).any() else 0.9


    indice = np.floor((xx - centro) / banda + 0.5).astype(int)
    toca_verde = (indice % 2) == 0

    # Camiseta LISA (los dos colores iguales, como la visitante o la de entreno): las bandas se
    # reparten por el ORIGEN de cada pixel, no por la geometria. El brillo que se conserva es el
    # del original, y el original TIENE rayas: repartiendo por bandas geometricas, la raya del
    # club seguia asomando por debajo del color nuevo. Separando "lo que era blanco" de "lo que
    # era verde" y midiendo cada uno contra SU referencia, las dos partes caen al mismo brillo y
    # lo unico que sobrevive son los pliegues, que es lo que se quiere.
    lisa = tuple(verde) == tuple(blanco)
    banda_clara = (camiseta & es_blanco) if lisa else (camiseta & ~toca_verde)
    banda_oscura = (camiseta & ~es_blanco) if lisa else (camiseta & toca_verde)

    salida = rgb.copy()
    # El blanco admite MUCHO menos juego que el verde: si se le deja bajar con la sombra, las
    # rayas blancas salen grises y la camiseta parece otra.
    for pinta, color, ref, (lo, hi) in (
        (banda_oscura, verde, ref_v, rango_verde),
        (banda_clara, blanco, ref_b, rango_blanco),
    ):
        if not pinta.any():
            continue
        factor = np.clip(lum[pinta] / max(ref, 0.05), lo, hi)[:, None]
        salida[pinta] = np.clip(np.array(color, dtype=np.float32) * factor, 0, 255)
    # PANTALON Y MEDIAS: verde liso del club. Salian de todo -uno con el pantalon casi menta, otro
    # con las medias de dos colores- y son la mitad de la equipacion. Se repinta de la camiseta
    # para abajo, sin llegar a las botas (el ultimo 12% de la figura), y sin tocar la piel.
    debajo = (yy > y_fin) & (yy < int(alto * 0.88)) & dentro & (~piel)
    # Todo lo que hay ahi es pantalon o medias: no hace falta adivinar el color, que es
    # justamente lo que fallaba (un pantalon menta no pasaba por "verde" y se quedaba menta).
    prenda = debajo
    if prenda.sum() > 500:
        ref_p = float(np.median(lum[debajo & es_verde])) if (debajo & es_verde).any() else 0.45
        factor = np.clip(lum[prenda] / max(ref_p, 0.05), 0.62, 1.30)[:, None]
        # El pantalon no siempre es del color de la camiseta: la turquesa lo lleva azul marino y
        # la blanca gris. Por defecto sigue siendo el mismo, que es la titular de siempre.
        salida[prenda] = np.clip(np.array(pantalon or verde, dtype=np.float32) * factor, 0, 255)

    a[:, :, :3] = salida
    return Image.fromarray(a.astype("uint8"), "RGBA")


def finish(origen, destino):
    # rembg se importa AQUI y no arriba: es lo unico que lo necesita, y arriba impedia
    # reutilizar el recoloreado (`uniformar_rayas`) desde otro script sin tenerlo instalado.
    from rembg import remove

    # El chandal es negro: el patrocinador tiene que ir en blanco o desaparece.
    chandal = "chandal" in os.path.basename(destino)
    fig = remove(Image.open(origen).convert("RGBA"))
    fig = fig.crop(fig.split()[3].getbbox())
    s = (CH * 0.99) / fig.size[1]
    if fig.size[0] * s > CW:
        s = (CW * 0.98) / fig.size[0]
    fig = fig.resize((int(fig.size[0] * s), int(fig.size[1] * s)))
    # ANTES de los logos: el escudo tambien lleva verde y blanco y no se puede repintar.
    fig = unificar_verde(fig)
    lienzo = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    lienzo.alpha_composite(fig, ((CW - fig.size[0]) // 2, CH - fig.size[1] - int(CH * 0.005)))

    cara = cara_de(lienzo)
    if cara is not None and not chandal:
        # Las rayas se pintan sobre el lienzo ya montado y ANTES de los logos: el escudo lleva
        # verde y blanco y no se puede repintar.
        lienzo = uniformar_rayas(lienzo, cara)
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
