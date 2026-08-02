from django.test import TestCase

from .models import Player, Team
from .universo_squad_import import (
    aplicar_plantilla,
    emparejar,
    importar_plantilla_de_universo,
    leer_fecha,
    url_de_foto,
)


class EmparejarTests(TestCase):
    """Casar la plantilla de Universo con la ficha sin adivinar: lo que no case, se dice."""

    def setUp(self):
        self.equipo = Team.objects.create(name="Cadete import", slug="cadete-import")
        self.uno = Player.objects.create(
            team=self.equipo, name="Neizan", full_name="Neizan González", number=1
        )
        self.dos = Player.objects.create(team=self.equipo, name="Adnan", full_name="Adnan", number=14)

    def test_casa_por_nombre_completo_aunque_cambie_el_orden(self):
        parejas, sueltos, sueltas = emparejar([self.uno], [{"name": "González Neizan"}])

        self.assertEqual(len(parejas), 1)
        self.assertEqual(parejas[0][0], self.uno)
        self.assertEqual(sueltos, [])
        self.assertEqual(sueltas, [])

    def test_si_el_nombre_no_casa_lo_intenta_por_dorsal(self):
        parejas, _, _ = emparejar([self.dos], [{"name": "Adnan El Mansouri", "dorsal": 14}])

        self.assertEqual(parejas[0][0], self.dos)

    def test_dice_quien_se_queda_fuera_por_cada_lado(self):
        parejas, sueltos, sueltas = emparejar([self.uno, self.dos], [{"name": "Jugador Desconocido"}])

        self.assertEqual(parejas, [])
        self.assertEqual(sorted(s.name for s in sueltos), ["Adnan", "Neizan"])
        self.assertEqual(sueltas, ["Jugador Desconocido"])


class AplicarPlantillaTests(TestCase):
    def setUp(self):
        self.equipo = Team.objects.create(name="Cadete aplicar", slug="cadete-aplicar", external_id="2749448")
        self.jugador = Player.objects.create(
            team=self.equipo, name="Lucas", full_name="Lucas Cecchetos", number=2
        )

    def test_rellena_la_posicion_que_falta(self):
        aplicar_plantilla(self.equipo, [{"name": "Lucas Cecchetos", "position": "Defensa", "dorsal": 2}])
        self.jugador.refresh_from_db()

        self.assertEqual(self.jugador.position, "Defensa")
        self.assertEqual(self.jugador.number, 2)

    def test_no_pisa_el_dorsal_que_puso_el_club(self):
        aplicar_plantilla(self.equipo, [{"name": "Lucas Cecchetos", "dorsal": 99}])
        self.jugador.refresh_from_db()

        self.assertEqual(self.jugador.number, 2)

    def test_con_sobrescribir_si_lo_pisa(self):
        aplicar_plantilla(self.equipo, [{"name": "Lucas Cecchetos", "dorsal": 99}], sobrescribir=True)
        self.jugador.refresh_from_db()

        self.assertEqual(self.jugador.number, 99)

    def test_sin_codigo_de_universo_lo_dice_claro(self):
        suelto = Team.objects.create(name="Sin codigo", slug="sin-codigo-import")

        with self.assertRaises(ValueError) as ctx:
            importar_plantilla_de_universo(suelto)

        self.assertIn("código de Universo", str(ctx.exception))

    def test_importa_con_el_fetch_inyectado(self):
        resumen = importar_plantilla_de_universo(
            self.equipo, fetch=lambda codigo: [{"name": "Lucas Cecchetos", "position": "Central"}]
        )

        self.assertEqual(resumen["filas_universo"], 1)
        self.assertEqual(resumen["no_estan_en_universo"], [])

    def test_solo_toca_a_los_que_ya_estan_en_la_ficha(self):
        """Regla del club: no se copia la plantilla entera, sólo se completa la suya."""
        antes = Player.objects.filter(team=self.equipo).count()

        resumen = importar_plantilla_de_universo(
            self.equipo,
            fetch=lambda codigo: [
                {"name": "Lucas Cecchetos", "dorsal": 2},
                {"name": "Chaval Que No Es Nuestro", "dorsal": 77},
            ],
        )

        self.assertEqual(Player.objects.filter(team=self.equipo).count(), antes)
        self.assertIn("Chaval Que No Es Nuestro", resumen["no_estan_en_la_ficha"])

    def test_se_puede_traer_de_otro_equipo_de_origen(self):
        """Los que suben de infantil están en la plantilla del equipo del año pasado."""
        pedidos = []

        importar_plantilla_de_universo(
            self.equipo,
            codigo="2749398",
            fetch=lambda codigo: (pedidos.append(codigo) or [{"name": "Lucas Cecchetos"}]),
        )

        self.assertEqual(pedidos, ["2749398"])


class DatosDeLaFilaCrudaTests(TestCase):
    """Universo mete la fecha y la foto en claves que cambian: se buscan por significado."""

    def setUp(self):
        self.equipo = Team.objects.create(name="Cadete raw", slug="cadete-raw", external_id="2749448")
        self.jugador = Player.objects.create(team=self.equipo, name="Iker", full_name="Iker Ruiz")

    def test_lee_la_fecha_en_los_formatos_de_universo(self):
        self.assertEqual(leer_fecha("14/03/2011").isoformat(), "2011-03-14")
        self.assertEqual(leer_fecha("2011-03-14T00:00:00").isoformat(), "2011-03-14")
        self.assertIsNone(leer_fecha("no es una fecha"))

    def test_completa_la_ruta_de_la_foto(self):
        self.assertEqual(url_de_foto("/media/x.jpg"), "https://www.universorfaf.es/media/x.jpg")
        self.assertEqual(url_de_foto("https://cdn/x.jpg"), "https://cdn/x.jpg")
        self.assertEqual(url_de_foto("null"), "")

    def test_rellena_nacimiento_y_guarda_la_foto(self):
        guardadas = []
        resumen = aplicar_plantilla(
            self.equipo,
            [{"name": "Iker Ruiz", "raw": {"fecha_nacimiento": "14/03/2011", "url_foto": "/media/iker.jpg"}}],
            descargar=lambda url: b"x" * 2000,
            guardar_foto=lambda jugador, contenido: guardadas.append((jugador.id, len(contenido))) or "guardada",
        )

        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.birth_date.isoformat(), "2011-03-14")
        self.assertEqual(resumen["fotos"], ["Iker"])
        self.assertEqual(guardadas, [(self.jugador.id, 2000)])

    def test_una_foto_que_no_baja_no_rompe_la_importacion(self):
        resumen = aplicar_plantilla(
            self.equipo,
            [{"name": "Iker Ruiz", "dorsal": 5, "raw": {"foto": "/media/roto.jpg"}}],
            descargar=lambda url: b"",
            guardar_foto=lambda jugador, contenido: "no deberia llamarse",
        )

        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.number, 5)
        self.assertEqual(resumen["fotos"], [])
