"""Dos garantías del modelo: que no estorba si no está, y que no filtra nombres.

La segunda es la importante. Manejas fichas de menores; que un nombre viaje a un tercero
gratuito porque a alguien se le olvidó taparlo no es un detalle.
"""
from django.test import SimpleTestCase, override_settings

from football import asistente_modelo as modelo


class ModeloTapaNombresTests(SimpleTestCase):
    def test_tapa_los_nombres_de_la_plantilla(self):
        frase = "anota como ausente a Nico Ruiz para el sábado"
        salida = modelo.tapar_nombres(frase, ["Nico Ruiz", "Harley"])
        self.assertNotIn("Nico", salida)
        self.assertNotIn("Ruiz", salida)
        self.assertIn("JUGADOR", salida)

    def test_no_deja_el_apellido_suelto(self):
        # De más largo a más corto: si se tapa "Nico" primero, "Nico Ruiz" acaba en
        # "JUGADOR Ruiz" y el apellido viaja igual.
        salida = modelo.tapar_nombres("marca a Nico Ruiz", ["Nico", "Nico Ruiz"])
        self.assertNotIn("Ruiz", salida)

    def test_no_le_afectan_las_mayusculas(self):
        salida = modelo.tapar_nombres("apunta que NICO RUIZ no vino", ["Nico Ruiz"])
        self.assertNotIn("NICO", salida.upper().replace("JUGADOR", ""))

    def test_ignora_nombres_demasiado_cortos(self):
        # Un nombre de dos letras taparía medio texto.
        salida = modelo.tapar_nombres("ve a la biblioteca", ["Al"])
        self.assertEqual(salida, "ve a la biblioteca")


class ModeloApagadoTests(SimpleTestCase):
    def test_sin_clave_no_se_llama_a_nadie(self):
        # Sin GROQ_API_KEY tiene que devolver None SIN salir a la red: si esto fallara, cada
        # frase que no entiende intentaría una conexión y sumaría segundos a tu petición.
        with override_settings():
            import os

            previa = os.environ.pop("GROQ_API_KEY", None)
            try:
                self.assertFalse(modelo.activo())
                self.assertIsNone(modelo.clasificar("ponme donde los entrenos"))
            finally:
                if previa is not None:
                    os.environ["GROQ_API_KEY"] = previa
