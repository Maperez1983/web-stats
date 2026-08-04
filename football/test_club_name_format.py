from django.test import SimpleTestCase, TestCase

from .club_name_format import formato_nombre_club
from .models import normalize_team_name_key


class FormatoDelNombreTests(SimpleTestCase):
    def test_deja_de_gritar(self):
        self.assertEqual(formato_nombre_club("ANTEQUERA CF SAD"), "Antequera CF SAD")

    def test_respeta_las_siglas_con_puntos(self):
        self.assertEqual(formato_nombre_club("C.D. RINCON"), "C.D. Rincon")
        self.assertEqual(formato_nombre_club("LA CALA C.D."), "La Cala C.D.")

    def test_los_articulos_del_toponimo_no_se_bajan(self):
        """"La Cala", "El Palo" y "El Ejido" son el nombre del sitio, no partículas."""
        self.assertEqual(formato_nombre_club("CD LA CALA"), "CD La Cala")
        self.assertEqual(formato_nombre_club("CD EL PALO FÚTBOL CLUB"), "CD El Palo Fútbol Club")
        self.assertEqual(
            formato_nombre_club("C.D. PVO. EL EJIDO 1969 S.A.D."), "C.D. Pvo. El Ejido 1969 S.A.D."
        )

    def test_una_abreviatura_no_es_una_sigla(self):
        """"STA." es Santa y "PTO." es Puerto: son palabras abreviadas, no siglas."""
        self.assertEqual(
            formato_nombre_club("U.D. STA. ROSALÍA MAQUEDA"), "U.D. Sta. Rosalía Maqueda"
        )
        self.assertEqual(
            formato_nombre_club("PTO. MALAGUEÑO CDAD JARDÍN G.I."), "Pto. Malagueño Cdad Jardín G.I."
        )

    def test_una_palabra_corta_no_es_una_sigla(self):
        self.assertEqual(formato_nombre_club("C.D. SANTA FE"), "C.D. Santa Fe")

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


class GrafiaDeLaFederacionTests(TestCase):
    """
    El mismo club escrito de dos formas: manda la del equipo que trae código federativo.
    """

    def _equipo(self, nombre, slug, external_id=""):
        from .models import Team

        return Team.objects.create(name=nombre, slug=slug, external_id=external_id)

    def test_manda_la_del_que_tiene_codigo_federativo(self):
        from .club_name_format import unificar_grafias

        senior = self._equipo("ALHAURIN DE LA TORRE C.F.", "alh-senior", external_id="12345")
        cadete = self._equipo("ALHAURÍN DE LA TORRE CF", "alh-cadete")

        unificar_grafias([senior, cadete])
        cadete.refresh_from_db()

        self.assertEqual(cadete.name, "ALHAURIN DE LA TORRE C.F.")

    def test_si_ninguno_tiene_codigo_no_se_elige_por_nosotros(self):
        from .club_name_format import unificar_grafias

        uno = self._equipo("CD LA CALA", "cala-1")
        otro = self._equipo("LA CALA C.D.", "cala-2")

        unificar_grafias([uno, otro])
        uno.refresh_from_db()
        otro.refresh_from_db()

        self.assertEqual(uno.name, "CD LA CALA")
        self.assertEqual(otro.name, "LA CALA C.D.")

    def test_si_todos_lo_escriben_igual_no_toca_nada(self):
        from .club_name_format import grafia_de_la_federacion

        a = self._equipo("C.D. RINCON", "rincon-a", external_id="802730")
        b = self._equipo("C.D. RINCON", "rincon-b")

        self.assertEqual(grafia_de_la_federacion([a, b]), {})
