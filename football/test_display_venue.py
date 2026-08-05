from django.test import SimpleTestCase

from football.templatetags.football_extras import display_venue


class DisplayVenueTests(SimpleTestCase):
    def test_nombre_normal_se_respeta(self):
        self.assertEqual(
            display_venue("Rincón de la Victoria - Benagalbón Campo Municipal"),
            "Rincón de la Victoria - Benagalbón Campo Municipal",
        )

    def test_url_pegada_no_se_imprime(self):
        self.assertEqual(
            display_venue("https://www.google.com/search?client=safari&q=campo+municipal"),
            "Ver ubicación (enlace)",
        )

    def test_url_troceada_por_el_movil_tambien(self):
        """Al copiar del iPhone la URL llega con espacios: "Https: //www. google. com/…"."""
        self.assertEqual(
            display_venue("Https: //www. google. com/search? client=safari CAÑADA+"),
            "Ver ubicación (enlace)",
        )

    def test_texto_largo_se_corta(self):
        largo = "Campo Municipal de " + ("Benagalbón " * 12)
        salida = display_venue(largo)
        self.assertTrue(salida.endswith("…"))
        self.assertLessEqual(len(salida), 60)

    def test_vacio(self):
        self.assertEqual(display_venue(""), "")
        self.assertEqual(display_venue(None), "")
