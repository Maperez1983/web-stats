"""Saca la porteria CENITAL de la foto del campo y la deja como recurso de la pizarra.

Las porterias que habia son de frente o en perspectiva: puestas sobre una tarea vista desde
arriba desentonan, y la premium en PNG trae ademas el tablero de transparencia pintado encima
(es RGB, no lleva alfa). La unica porteria fotografica y cenital que tiene el proyecto esta
dentro de coach_home_pitch_surface.png, que es el mismo cesped que se usa de fondo.

El alfa no se recorta a mano: se calcula por "lo poco verde que es cada pixel". Los postes salen
opacos y la red translucida, asi que la hierba se ve a traves de la malla y la porteria se posa
sobre la tarea en vez de flotar encima.

    python3 scripts/extraer_porteria_cenital.py

Escribe dos: la que mira a la derecha (va en el fondo izquierdo del campo) y su espejo.
"""
import os

import numpy as np
from PIL import Image, ImageOps

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(RAIZ, "football", "static", "football", "images")
CAMPO = os.path.join(IMG, "pitch3d", "coach_home_pitch_surface.png")
DESTINO = os.path.join(IMG, "goals")

# Recorte de la porteria del fondo izquierdo, sin la linea de fondo (que se cuela por la derecha).
RECORTE = (6, 371, 62, 570)
AUMENTO = 5  # el original mide 56x199: a 5x aguanta el tamaño al que se usa en el lienzo


def extraer():
    rec = Image.open(CAMPO).convert("RGB").crop(RECORTE)
    a = np.asarray(rec).astype(np.float32)
    verdor = a[:, :, 1] - (a[:, :, 0] + a[:, :, 2]) / 2.0
    brillo = a.max(axis=2)
    alfa = np.clip(1.0 - verdor / 26.0, 0, 1) * np.clip((brillo - 70) / 60.0, 0, 1)
    pieza = Image.merge("RGBA", (*rec.split(), Image.fromarray((alfa * 255).astype(np.uint8))))
    return pieza.resize((pieza.width * AUMENTO, pieza.height * AUMENTO), Image.LANCZOS)


def main():
    pieza = extraer()
    # En la foto la porteria esta en el fondo izquierdo, o sea que su boca mira a la DERECHA.
    for nombre, imagen in (
        ("porteria_cenital_izq.png", pieza),                  # fondo izquierdo, boca a la derecha
        ("porteria_cenital_der.png", ImageOps.mirror(pieza)),  # fondo derecho, boca a la izquierda
    ):
        ruta = os.path.join(DESTINO, nombre)
        # A paleta: el ruido fotografico de la red hincha el PNG a 280 KB por porteria y a la
        # vista no se distingue. Con 96 colores baja a ~55 KB y el alfa se mantiene.
        imagen.quantize(colors=96, method=Image.FASTOCTREE).save(ruta, optimize=True)
        print(f"hecho: {ruta} {imagen.size} {os.path.getsize(ruta) // 1024} KB")


if __name__ == "__main__":
    main()
