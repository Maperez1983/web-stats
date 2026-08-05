"""El recorte de los avatares que se suben a mano.

Se mide contra las figuras de la biblioteca, que traen alfa de verdad: se
aplastan sobre blanco (que es lo que da FLUX) y se comprueba que al recortarlas
no se come nada del jugador.
"""
import io
import os

import numpy as np
from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from football.avatar_cutout import recortar_fondo, ya_viene_recortado

BIBLIOTECA = os.path.join(
    settings.BASE_DIR, "football", "static", "football", "images",
    "coach_roster_avatars", "library",
)
FIGURAS = ["kit_home_hd.png", "kit_away_hd.png", "gk_blue_hd.png", "chandal_black.png"]


def _png(imagen):
    buf = io.BytesIO()
    imagen.save(buf, "PNG")
    return buf.getvalue()


class AvatarCutoutTests(SimpleTestCase):
    def test_lo_ya_recortado_no_se_toca(self):
        for nombre in FIGURAS:
            with self.subTest(nombre):
                datos = _png(Image.open(os.path.join(BIBLIOTECA, nombre)).convert("RGBA"))
                self.assertTrue(ya_viene_recortado(datos))
                self.assertIs(recortar_fondo(datos), datos)

    def test_recorta_el_fondo_sin_comerse_al_jugador(self):
        for nombre in FIGURAS:
            with self.subTest(nombre):
                original = Image.open(os.path.join(BIBLIOTECA, nombre)).convert("RGBA")
                alfa_bueno = np.array(original)[:, :, 3]
                plano = Image.new("RGB", original.size, (255, 255, 255))
                plano.paste(original, (0, 0), original)

                salida = recortar_fondo(_png(plano))
                alfa = np.array(Image.open(io.BytesIO(salida)).convert("RGBA"))[:, :, 3]

                cuerpo = alfa_bueno > 200
                fondo = alfa_bueno < 10
                comido = float(((alfa < 10) & cuerpo).sum()) / max(1, int(cuerpo.sum()))
                quitado = float(((alfa < 10) & fondo).sum()) / max(1, int(fondo.sum()))
                self.assertLess(comido, 0.01, "se esta comiendo parte del jugador")
                self.assertGreater(quitado, 0.90, "no esta quitando el fondo")
