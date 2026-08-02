from django.test import SimpleTestCase

from .views import _split_venue_text_and_link


class CampoDeJuegoConEnlaceTests(SimpleTestCase):
    """
    En la portada se llegó a pintar una búsqueda de Google como si fuera el campo de juego:
    alguien la pegó en el estadio del equipo y el alta de partido la copió tal cual.
    """

    def test_un_nombre_normal_se_respeta(self):
        texto, enlace = _split_venue_text_and_link("Benagalbón Campo Municipal")

        self.assertEqual(texto, "Benagalbón Campo Municipal")
        self.assertEqual(enlace, "")

    def test_una_url_sola_no_es_el_nombre_del_campo(self):
        texto, enlace = _split_venue_text_and_link("https://www.google.com/search?q=Campo+Municipal")

        self.assertEqual(texto, "")
        self.assertTrue(enlace.startswith("https://"))

    def test_nombre_y_enlace_mezclados_se_separan(self):
        texto, enlace = _split_venue_text_and_link(
            "Campo Municipal La Cañada https://maps.google.com/?q=cañada"
        )

        self.assertEqual(texto, "Campo Municipal La Cañada")
        self.assertEqual(enlace, "https://maps.google.com/?q=cañada")

    def test_sin_esquema_tambien_se_reconoce(self):
        texto, enlace = _split_venue_text_and_link("www.google.com/search?q=campo")

        self.assertEqual(texto, "")
        self.assertEqual(enlace, "https://www.google.com/search?q=campo")

    def test_vacio_no_revienta(self):
        self.assertEqual(_split_venue_text_and_link(None), ("", ""))
