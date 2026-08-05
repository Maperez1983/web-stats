"""Recorte de fondo para los avatares que se suben a mano.

La pantalla de subir avatares guardaba el PNG tal cual. Los avatares se generan
con FLUX, que NO produce transparencia: salen opacos, asi que en la pizarra
aparecian con su recuadro de fondo en vez de recortados.

Aqui se reutiliza el mismo recortador que ya usa el generador de kits 2D
(grabcut de OpenCV). No se toca lo que ya viene recortado: si la imagen trae
alfa de verdad, se devuelve intacta.
"""
import io

import numpy as np
from PIL import Image


def ya_viene_recortado(datos: bytes, minimo_transparente: float = 0.04) -> bool:
    """True si el PNG ya trae un alfa util (mas de un 4% de pixeles a cero)."""
    try:
        im = Image.open(io.BytesIO(datos))
        if im.mode not in ("RGBA", "LA", "P"):
            return False
        alfa = np.array(im.convert("RGBA"))[:, :, 3]
        return float((alfa < 10).sum()) / max(1, alfa.size) >= minimo_transparente
    except Exception:
        # Ante la duda, no tocar: es peor romper un avatar bueno que dejar un fondo.
        return True


def recortar_fondo(datos: bytes, tolerancia: int = 6) -> bytes:
    """Devuelve el PNG con el fondo a transparente. Si algo falla, el original.

    Se rellena desde los CUATRO BORDES hacia dentro, no por segmentacion. El
    grabcut del generador de kits esta afinado para una camiseta y con una
    persona entera se come la cabeza y las zapatillas. El relleno por bordes
    solo quita lo que esta pegado al marco, asi que las rayas blancas de la
    camiseta y las botas blancas se quedan donde estan.

    La tolerancia 6 no es a ojo: medida contra las figuras de la biblioteca
    -que traen alfa de verdad- come el 0% del jugador y quita el 96-98% del
    fondo. Con 8 ya se traga media figura de portero, y con 10 la amarilla.
    """
    if not datos or ya_viene_recortado(datos):
        return datos
    try:
        import cv2

        im = Image.open(io.BytesIO(datos)).convert("RGB")
        bgr = np.array(im)[:, :, ::-1].copy()
        alto, ancho = bgr.shape[:2]
        mascara = np.zeros((alto + 2, ancho + 2), np.uint8)
        semillas = [(0, 0), (ancho - 1, 0), (0, alto - 1), (ancho - 1, alto - 1),
                    (ancho // 2, 0), (ancho // 2, alto - 1)]
        banderas = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
        for sx, sy in semillas:
            cv2.floodFill(bgr, mascara, (int(sx), int(sy)), 0,
                          (tolerancia,) * 3, (tolerancia,) * 3, banderas)
        fondo = mascara[1:-1, 1:-1] > 0
        if fondo.mean() < 0.05 or fondo.mean() > 0.92:
            # Ni hay fondo que quitar, ni vale la pena arriesgarse a borrar al jugador.
            return datos
        alfa = np.where(fondo, 0, 255).astype(np.uint8)
        # borde suave: sin esto el recorte queda con dientes de sierra
        alfa = cv2.GaussianBlur(alfa, (0, 0), 0.8)
        rgba = np.dstack([np.array(im), alfa])
        salida = io.BytesIO()
        Image.fromarray(rgba.astype(np.uint8)).save(salida, "PNG")
        return salida.getvalue()
    except Exception:
        return datos
