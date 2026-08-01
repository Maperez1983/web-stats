from django.test import SimpleTestCase, TestCase

from .models import Team
from .universo_venue_services import (
    aplicar_campo_de_juego,
    extraer_campo_de_juego,
    sincronizar_campos_de_equipos,
)


class ExtraerCampoDeJuegoTests(SimpleTestCase):
    """La ficha de Universo no publica esquema: se busca por nombre de clave, no por ruta."""

    def test_saca_campo_y_compone_la_direccion(self):
        payload = {
            "equipo": {
                "nombre": "C.D. EJEMPLO",
                "instalacion": "CAMPO MUNICIPAL LOS OLIVOS",
                "direccion": "Calle Real, 12",
                "codigo_postal": "29730",
                "localidad": "Rincón de la Victoria",
            }
        }

        datos = extraer_campo_de_juego(payload)

        self.assertEqual(datos["name"], "CAMPO MUNICIPAL LOS OLIVOS")
        self.assertEqual(datos["address"], "Calle Real, 12, 29730, Rincón de la Victoria")
        self.assertIn("google.com/maps", datos["maps_url"])

    def test_lo_encuentra_aunque_venga_anidado_y_con_otra_grafia(self):
        payload = {"data": [{"detalle": {"des_instalacion": "ESTADIO FRANCISCO ROMERO"}}]}

        self.assertEqual(extraer_campo_de_juego(payload)["name"], "ESTADIO FRANCISCO ROMERO")

    def test_ignora_los_huecos_disfrazados(self):
        payload = {"campo": "-", "direccion": "N/A", "localidad": ""}

        datos = extraer_campo_de_juego(payload)

        self.assertEqual(datos["name"], "")
        self.assertEqual(datos["address"], "")

    def test_payload_inservible_no_revienta(self):
        self.assertEqual(extraer_campo_de_juego(None)["name"], "")


class AplicarYSincronizarTests(TestCase):
    def setUp(self):
        self.equipo = Team.objects.create(name="C.D. Ejemplo", slug="cd-ejemplo-v", external_id="C1")

    def test_por_defecto_solo_rellena_huecos(self):
        self.equipo.home_stadium = "LO QUE PUSE A MANO"
        self.equipo.save(update_fields=["home_stadium"])

        aplicar_campo_de_juego(self.equipo, {"name": "OTRO CAMPO", "address": "Calle X"})
        self.equipo.refresh_from_db()

        self.assertEqual(self.equipo.home_stadium, "LO QUE PUSE A MANO")
        self.assertEqual(self.equipo.home_stadium_address, "Calle X")

    def test_con_sobrescribir_corrige_el_dato_malo(self):
        self.equipo.home_stadium = "FRANCISCO CARRASCO"
        self.equipo.save(update_fields=["home_stadium"])

        aplicar_campo_de_juego(self.equipo, {"name": "ESTADIO FRANCISCO ROMERO"}, sobrescribir=True)
        self.equipo.refresh_from_db()

        self.assertEqual(self.equipo.home_stadium, "ESTADIO FRANCISCO ROMERO")

    def test_el_resumen_dice_quien_se_queda_fuera_y_por_que(self):
        sin_codigo = Team.objects.create(name="Amistoso S.C.", slug="amistoso-v")
        falla = Team.objects.create(name="Rompe F.C.", slug="rompe-v", external_id="C2")

        def fetch(codigo):
            if codigo == "C2":
                raise ValueError("sesión caducada")
            return {"instalacion": "CAMPO MUNICIPAL"}

        resumen = sincronizar_campos_de_equipos([self.equipo, sin_codigo, falla], fetch=fetch)

        self.assertEqual(len(resumen["actualizados"]), 1)
        self.assertIn("Amistoso S.C.", resumen["sin_codigo"])
        self.assertTrue(any("Rompe F.C." in e for e in resumen["errores"]))
