"""El extractor de color del escudo, medido contra escudos de verdad.

No se prueba "que devuelva algo": se prueba que el color propuesto sea del TONO
correcto para escudos conocidos, y que el negro y el blanco entren como ribete
-que es donde fallaba: a un club negro y amarillo le proponia ribete blanco-.
"""
import colorsys
import io

from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from football.crest_colors import colores_de_escudo, equipacion_propuesta


def _escudo(fondo, detalle=None, con_negro=False):
    im = Image.new("RGBA", (200, 220), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, 190, 210], radius=18, fill=fondo)
    if detalle:
        d.rounded_rectangle([70, 70, 130, 150], radius=8, fill=detalle)
    if con_negro:
        d.rounded_rectangle([10, 10, 190, 210], radius=18, outline=(10, 10, 10, 255), width=26)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _tono(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


class CrestColorsTests(SimpleTestCase):
    def test_saca_el_color_dominante(self):
        for nombre, fondo, tono_esperado in [
            ("verde", (5, 130, 60, 255), 140),
            ("rojo", (200, 30, 30, 255), 0),
            ("azul", (20, 60, 170, 255), 225),
        ]:
            with self.subTest(nombre):
                p = equipacion_propuesta(_escudo(fondo))
                diferencia = abs((_tono(p["home_main"]) - tono_esperado + 180) % 360 - 180)
                self.assertLess(diferencia, 25, f"{nombre}: propuso {p['home_main']}")

    def test_el_negro_entra_como_ribete(self):
        # Un escudo amarillo con mucho negro es un clasico (Cantoria). Antes se le
        # proponia ribete blanco porque el negro se descartaba del todo.
        p = equipacion_propuesta(_escudo((246, 218, 13, 255), con_negro=True))
        self.assertGreater(p["negro_pct"], 10)
        self.assertEqual(p["home_trim"], "#111418")

    def test_sin_color_util_no_inventa(self):
        blanco = _escudo((255, 255, 255, 255))
        self.assertEqual(colores_de_escudo(blanco), [])
        self.assertEqual(equipacion_propuesta(blanco), {})
