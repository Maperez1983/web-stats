"""La telestración quemada dentro del vídeo."""
from django.test import SimpleTestCase

from football.video_burn import _color, _puntos_de, capa_png


class CapaDeDibujoTests(SimpleTestCase):
    def test_sin_objetos_no_hay_capa(self):
        self.assertIsNone(capa_png({}, ancho=1280, alto=720))
        self.assertIsNone(capa_png({"objects": []}, ancho=1280, alto=720))

    def test_la_capa_sale_del_tamano_del_video(self):
        from PIL import Image
        import io

        png = capa_png({"objects": [
            {"type": "line", "left": 10, "top": 10, "x1": 0, "y1": 0, "x2": 100, "y2": 40,
             "stroke": "#6fd3ff", "strokeWidth": 4},
        ]}, ancho=1280, alto=720)
        self.assertIsNotNone(png)
        self.assertEqual(Image.open(io.BytesIO(png)).size, (1280, 720))

    def test_una_forma_desconocida_no_tumba_la_exportacion(self):
        png = capa_png({"objects": [{"type": "holograma", "left": 0, "top": 0}]},
                       ancho=640, alto=360)
        self.assertIsNotNone(png, "se ignora la forma rara, no se cae el vídeo")

    def test_el_lienzo_del_editor_se_reescala_al_video(self):
        # Dibujado en un reproductor de 640 y quemado en un vídeo de 1280: todo x2.
        puntos = _puntos_de({"type": "line", "left": 100, "top": 100, "x1": 0, "y1": 0,
                             "x2": 100, "y2": 0}, escala=2.0)
        self.assertEqual(len(puntos), 2)
        self.assertAlmostEqual(puntos[1][0] - puntos[0][0], 200.0, places=1)

    def test_colores_de_fabric(self):
        self.assertEqual(_color("#6fd3ff"), (111, 211, 255, 255))
        self.assertEqual(_color("#fff"), (255, 255, 255, 255))
        self.assertEqual(_color("rgba(255, 0, 0, 0.5)")[:3], (255, 0, 0))
        self.assertIsNone(_color("none"), "sin relleno es sin relleno, no negro")
