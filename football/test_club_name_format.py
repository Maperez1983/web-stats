from django.test import SimpleTestCase, TestCase

from .club_name_format import formato_nombre_club
from .models import normalize_team_name_key


class FormatoDelNombreTests(SimpleTestCase):
    def test_deja_de_gritar(self):
        self.assertEqual(formato_nombre_club("ANTEQUERA CF SAD"), "Antequera CF SAD")

    def test_respeta_las_siglas_con_puntos(self):
        self.assertEqual(formato_nombre_club("C.D. RINCON"), "C.D. Rincon")
        self.assertEqual(formato_nombre_club("LA CALA C.D."), "La Cala C.D.")

    def test_las_particulas_van_en_minuscula(self):
        self.assertEqual(
            formato_nombre_club("ALHAURIN DE LA TORRE C.F."), "Alhaurin de la Torre C.F."
        )

    def test_pero_no_al_principio(self):
        self.assertEqual(formato_nombre_club("LA CALA"), "La Cala")

    def test_respeta_los_guiones(self):
        self.assertEqual(formato_nombre_club("CARO-ACCINO RUBIO"), "Caro-Accino Rubio")

    def test_no_inventa_tildes(self):
        """Poner "Alhaurín" donde la federación escribió "ALHAURIN" es cambiar el dato."""
        self.assertEqual(formato_nombre_club("ALHAURIN"), "Alhaurin")

    def test_lo_que_ya_esta_bien_no_se_estropea(self):
        for bueno in ["Atlético Jaén F.C.", "Benagalbón Cadete", "Mijas Las Lagunas B"]:
            self.assertEqual(formato_nombre_club(bueno), bueno)

    def test_vacio_no_revienta(self):
        self.assertEqual(formato_nombre_club(None), "")
        self.assertEqual(formato_nombre_club("   "), "")


class NoRompeElEmparejadoTests(SimpleTestCase):
    """
    Lo importante: `name_key` es la clave con la que la clasificación empareja cada fila de la
    tabla con su equipo. Cambiar el formato NO puede cambiarla.
    """

    def test_la_clave_de_emparejado_no_cambia(self):
        for nombre in [
            "ALHAURIN DE LA TORRE C.F.",
            "C.D. RINCON",
            "CD PIZARRA ATLÉTICO",
            "ANTEQUERA CF SAD",
            "U.D. STA. ROSALÍA MAQUEDA",
            "RINCÓN DE LA VICTORIA",
        ]:
            self.assertEqual(
                normalize_team_name_key(nombre),
                normalize_team_name_key(formato_nombre_club(nombre)),
                f"El formateo cambió la clave de emparejado de {nombre}",
            )


class AplicarloATodosTests(TestCase):
    def test_cambia_los_que_gritan_y_deja_los_demas(self):
        from .club_name_format import aplicar
        from .models import Team

        grita = Team.objects.create(name="ANTEQUERA CF SAD", slug="antequera-fmt")
        bueno = Team.objects.create(name="Atlético Jaén F.C.", slug="jaen-fmt")

        resumen = aplicar([grita, bueno])
        grita.refresh_from_db()
        bueno.refresh_from_db()

        self.assertEqual(grita.name, "Antequera CF SAD")
        self.assertEqual(bueno.name, "Atlético Jaén F.C.")
        self.assertEqual(len(resumen["cambiados"]), 1)

    def test_la_clave_de_emparejado_sobrevive(self):
        from .club_name_format import aplicar
        from .models import Team

        equipo = Team.objects.create(name="C.D. RINCON", slug="rincon-fmt")
        clave_antes = equipo.name_key

        aplicar([equipo])
        equipo.refresh_from_db()

        self.assertEqual(equipo.name, "C.D. Rincon")
        self.assertEqual(equipo.name_key, clave_antes)
