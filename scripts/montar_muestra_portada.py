"""Monta la muestra de la portada de Entrenamiento: una tarea con los recursos DE VERDAD.

La portada era tres cajas de texto. Esto enseña el producto sin prometer nada: el cesped es el
campo HD del propio proyecto y las fichas son las chapas del club, los conos, el balon y la
porteria que el entrenador se va a encontrar dentro del editor. Nada de foto de banco.

Se lee de izquierda a derecha como se lee una tarea: rondo -> conduccion -> finalizacion.

    python3 scripts/montar_muestra_portada.py

Escribe football/static/football/images/task_builder/muestra_tarea_recursos.jpg (~120 KB).
La plantilla que la usa es sessions_planner.html (.muestra-tarea) y hay un test que comprueba
que el fichero existe y que NO va con loading="lazy".
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(RAIZ, "football", "static", "football", "images")
PIEZAS = os.path.join(RAIZ, "scripts", "muestra_piezas")
CAMPO = os.path.join(IMG, "pitch3d", "coach_home_pitch_surface.png")

ANCHO, ALTO = 1600, 340
BLANCO = (255, 255, 255, 236)
ORO = (255, 200, 20, 240)


def cesped():
    """Banda de cesped a partir del campo HD, por una zona sin lineas ni areas.

    El trozo se espeja al repetir: pegado tal cual se ve la costura en cada union.
    """
    trozo = Image.open(CAMPO).convert("RGB").crop((345, 120, 690, 860))
    ancho_final = max(1, int(trozo.width * ALTO / trozo.height))
    veces = ANCHO // ancho_final + 2
    tira = Image.new("RGB", (trozo.width * veces, trozo.height))
    for i in range(veces):
        tira.paste(trozo if i % 2 == 0 else ImageOps.mirror(trozo), (i * trozo.width, 0))
    tira = tira.resize((ancho_final * veces, ALTO), Image.LANCZOS)
    x0 = (tira.width - ANCHO) // 2
    return tira.crop((x0, 0, x0 + ANCHO, ALTO))


def porteria():
    """Recorta la porteria REAL del campo HD y le calcula el alfa por 'lo poco verde que es'.

    Ninguna de las porterias sueltas del proyecto sirve aqui: la premium en PNG trae el tablero
    de transparencia pintado encima, y las planas desentonan sobre una foto. Esta sale de la
    misma imagen que el cesped, asi que casa la luz y la red deja pasar la hierba.
    """
    rec = Image.open(CAMPO).convert("RGB").crop((6, 371, 62, 570))
    a = np.asarray(rec).astype(np.float32)
    verdor = a[:, :, 1] - (a[:, :, 0] + a[:, :, 2]) / 2.0
    brillo = a.max(axis=2)
    alfa = np.clip(1.0 - verdor / 26.0, 0, 1) * np.clip((brillo - 70) / 60.0, 0, 1)
    pieza = Image.merge("RGBA", (*rec.split(), Image.fromarray((alfa * 255).astype(np.uint8))))
    pieza = ImageOps.mirror(pieza)  # que la boca mire a la izquierda, de donde viene el ataque
    return pieza.resize((pieza.width * 6, pieza.height * 6), Image.LANCZOS)


def pegar(lienzo, pieza, centro, alto, sombra=True):
    """Pega un recurso centrado en `centro` con la altura pedida, con su sombra en el suelo."""
    if isinstance(pieza, str):
        pieza = Image.open(pieza).convert("RGBA")
    ancho = max(1, int(pieza.width * alto / pieza.height))
    pieza = pieza.resize((ancho, alto), Image.LANCZOS)
    cx, cy = centro
    if sombra:
        # La sombra va en su propia capa y desenfocada: pegar la pieza en negro la deja recortada.
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        rx, ry = ancho * 0.46, alto * 0.20
        ImageDraw.Draw(capa).ellipse(
            [cx - rx, cy + alto * 0.30 - ry, cx + rx, cy + alto * 0.30 + ry], fill=(0, 0, 0, 92))
        lienzo.alpha_composite(capa.filter(ImageFilter.GaussianBlur(7)))
    lienzo.alpha_composite(pieza, (int(cx - ancho / 2), int(cy - alto / 2)))


def punta(dib, x, y, ang, color, tam=20):
    dib.polygon([
        (x, y),
        (x - tam * math.cos(ang - 0.42), y - tam * math.sin(ang - 0.42)),
        (x - tam * math.cos(ang + 0.42), y - tam * math.sin(ang + 0.42)),
    ], fill=color)


def flecha(dib, desde, hasta, color=BLANCO, grosor=6, guiones=True, margen=(48, 48)):
    """Pase o desplazamiento. Se retranquea en los dos extremos para no pisar las chapas."""
    (x1, y1), (x2, y2) = desde, hasta
    ang = math.atan2(y2 - y1, x2 - x1)
    largo = math.hypot(x2 - x1, y2 - y1) - margen[0] - margen[1]
    if largo <= 12:
        return
    x1, y1 = x1 + math.cos(ang) * margen[0], y1 + math.sin(ang) * margen[0]
    x2, y2 = x1 + math.cos(ang) * largo, y1 + math.sin(ang) * largo
    if guiones:
        trozo, hueco, t = 24, 15, 0
        while t < largo:
            a = min(t + trozo, largo)
            dib.line([x1 + math.cos(ang) * t, y1 + math.sin(ang) * t,
                      x1 + math.cos(ang) * a, y1 + math.sin(ang) * a], fill=color, width=grosor)
            t = a + hueco
    else:
        dib.line([x1, y1, x2, y2], fill=color, width=grosor)
    punta(dib, x2, y2, ang, color)


def recorrido(dib, puntos, color=ORO, grosor=6):
    """Conduccion entre conos: linea continua que los va sorteando, con punta al final."""
    dib.line([c for p in puntos for c in p], fill=color, width=grosor, joint="curve")
    (xa, ya), (xb, yb) = puntos[-2], puntos[-1]
    punta(dib, xb, yb, math.atan2(yb - ya, xb - xa), color)


def montar():
    lienzo = cesped().convert("RGBA")
    dib = ImageDraw.Draw(lienzo, "RGBA")
    CHAPA = 74
    local = os.path.join(IMG, "chapa", "chapa_local.png")
    cono = os.path.join(IMG, "task_builder", "ppt", "cone_ppt.png")

    # --- 1. Rondo: cinco por fuera tocando, uno dentro persiguiendo -------------------------
    cx, cy = 306, 170
    fuera = [(cx + 150 * math.cos(math.radians(a)), cy + 100 * math.sin(math.radians(a)))
             for a in (198, 270, 342, 54, 126)]
    for i in range(4):
        flecha(dib, fuera[i], fuera[i + 1], margen=(46, 46))
    for dx, dy in ((-226, -132), (226, -132), (-226, 132), (226, 132)):
        pegar(lienzo, cono, (cx + dx, cy + dy), 44)
    for p in fuera:
        pegar(lienzo, local, p, CHAPA)
    pegar(lienzo, os.path.join(IMG, "chapa", "chapa_turquesa.png"), (cx, cy), CHAPA)

    # --- 2. Conduccion: el balon sale del rondo y sortea los conos --------------------------
    conos_x = (680, 780, 880, 980)
    for x in conos_x:
        pegar(lienzo, cono, (x, 170), 44)
    # Onda: roza cada cono por un lado distinto y cruza la linea entre cono y cono.
    onda = [(x, 170 + 54 * math.cos(math.pi * (x - conos_x[0]) / 100))
            for x in range(618, 1031, 7)]
    recorrido(dib, onda + [(1058, 146)])
    pegar(lienzo, local, (566, 170), CHAPA)
    pegar(lienzo, os.path.join(PIEZAS, "balon_premium.png"), (608, 202), 38, sombra=False)

    # --- 3. Finalizacion: apoyo, pase y remate a porteria con portero -----------------------
    pegar(lienzo, porteria(), (1518, 170), 214, sombra=False)
    pegar(lienzo, os.path.join(IMG, "chapa", "chapa_gk_azul.png"), (1462, 170), CHAPA)
    pegar(lienzo, local, (1146, 76), CHAPA)
    pegar(lienzo, local, (1230, 254), CHAPA)
    flecha(dib, (1146, 76), (1230, 254), margen=(44, 46))
    flecha(dib, (1230, 254), (1468, 178), color=ORO, guiones=False, margen=(46, 44))

    # Velo suave por los bordes: la banda se funde con el panel en vez de cortarse en seco.
    velo = Image.new("L", (ANCHO, ALTO), 0)
    vd = ImageDraw.Draw(velo)
    for i in range(64):
        vd.rectangle([i, i, ANCHO - 1 - i, ALTO - 1 - i], outline=int(86 * (1 - i / 64) ** 2))
    lienzo.alpha_composite(Image.merge("RGBA", (
        Image.new("L", (ANCHO, ALTO), 6), Image.new("L", (ANCHO, ALTO), 14),
        Image.new("L", (ANCHO, ALTO), 24), velo)))

    salida = os.path.join(IMG, "task_builder", "muestra_tarea_recursos.jpg")
    lienzo.convert("RGB").save(salida, quality=84, optimize=True, progressive=True)
    print(f"hecho: {salida} {lienzo.size} {os.path.getsize(salida) // 1024} KB")


if __name__ == "__main__":
    montar()
