from django.test import SimpleTestCase, TestCase

from .models import Competition, Group, Season, Team
from .team_category_services import categoria_para_equipo, deducir_categoria, rellenar_categorias


class DeducirCategoriaTests(SimpleTestCase):
    """La categoría no se inventa: sale de donde la escribe la federación."""

    def test_la_saca_del_nombre_de_la_competicion(self):
        self.assertEqual(deducir_categoria("Grupo 1 (Málaga)", "3ª División Andaluza Cadete"), "Cadete")

    def test_prebenjamin_no_se_confunde_con_benjamin(self):
        self.assertEqual(deducir_categoria("Copa Federación 3ª Andaluza Prebenjamín"), "Prebenjamín")
        self.assertEqual(deducir_categoria("Liga Benjamín Grupo 2"), "Benjamín")

    def test_el_senior_se_reconoce_aunque_no_lleve_la_palabra(self):
        self.assertEqual(deducir_categoria("Grupo 2", "División de Honor Andaluza"), "Senior")

    def test_sin_pistas_devuelve_vacio(self):
        self.assertEqual(deducir_categoria("Grupo 1", "Liga"), "")

    def test_tolera_acentos_y_mayusculas(self):
        self.assertEqual(deducir_categoria("3ª DIVISIÓN ANDALUZA CADETE"), "Cadete")


class RellenarCategoriasTests(TestCase):
    def setUp(self):
        competicion = Competition.objects.create(name="3ª División Andaluza Cadete", slug="cad-cat")
        temporada = Season.objects.create(competition=competicion, name="2026/2027")
        self.grupo = Group.objects.create(season=temporada, name="Grupo 1 (Málaga)", slug="g1-cat")

    def test_rellena_los_vacios(self):
        equipo = Team.objects.create(name="CD Ejemplo", slug="cd-ejemplo-cat", group=self.grupo)

        rellenar_categorias([equipo])
        equipo.refresh_from_db()

        self.assertEqual(equipo.category, "Cadete")

    def test_no_pisa_lo_que_puso_el_club(self):
        equipo = Team.objects.create(
            name="CD Ejemplo B", slug="cd-ejemplo-b-cat", group=self.grupo, category="Cadete A"
        )

        rellenar_categorias([equipo])
        equipo.refresh_from_db()

        self.assertEqual(equipo.category, "Cadete A")

    def test_con_overwrite_si_lo_pisa(self):
        equipo = Team.objects.create(
            name="CD Ejemplo C", slug="cd-ejemplo-c-cat", group=self.grupo, category="lo que sea"
        )

        rellenar_categorias([equipo], sobrescribir=True)
        equipo.refresh_from_db()

        self.assertEqual(equipo.category, "Cadete")

    def test_un_equipo_sin_grupo_no_revienta(self):
        suelto = Team.objects.create(name="Rival de amistoso", slug="rival-suelto-cat")

        resumen = rellenar_categorias([suelto])

        self.assertEqual(categoria_para_equipo(suelto), "")
        self.assertIn("Rival de amistoso", resumen["sin_pistas"])


class EquipoNuevoNaceConCategoriaTests(TestCase):
    """Lo que entra por importación tiene que cumplir la regla desde el minuto uno."""

    def setUp(self):
        competicion = Competition.objects.create(name="3ª División Andaluza Cadete", slug="cad-nuevo")
        temporada = Season.objects.create(competition=competicion, name="2026/2027")
        self.grupo = Group.objects.create(season=temporada, name="Grupo 1", slug="g1-nuevo")

    def test_al_crearlo_con_grupo_hereda_la_categoria(self):
        from .models import resolve_or_create_team

        equipo, creado = resolve_or_create_team(name="CD Recién Llegado", group=self.grupo)

        self.assertTrue(creado)
        self.assertEqual(equipo.category, "Cadete")

    def test_si_le_pasan_categoria_manda_la_suya(self):
        from .models import resolve_or_create_team

        equipo, _ = resolve_or_create_team(
            name="CD Con Categoría", group=self.grupo, defaults={"category": "Cadete B"}
        )

        self.assertEqual(equipo.category, "Cadete B")


class CategoriaPorLosPartidosTests(TestCase):
    """
    Los rivales de amistoso se crean a mano: sin grupo ni competición no hay nada que deducir.
    Pero contra quién juegan sí lo dice.
    """

    def setUp(self):
        from datetime import date

        from .models import Competition, Match, Season, Team

        competicion = Competition.objects.create(name="Amistosos cat")
        self.temporada = Season.objects.create(
            competition=competicion, name="2026/2027", start_date=date(2026, 7, 1)
        )
        self.cadete = Team.objects.create(
            name="Mi Cadete cat", slug="mi-cadete-cat", category="CADETE", is_primary=True
        )
        self.senior = Team.objects.create(
            name="Mi Senior cat", slug="mi-senior-cat", category="SENIOR", is_primary=True
        )
        self.rival = Team.objects.create(name="Rival amistoso cat", slug="rival-amistoso-cat")
        self.Match = Match

    def _partido(self, local, visitante):
        from datetime import date

        return self.Match.objects.create(
            home_team=local, away_team=visitante, date=date(2026, 8, 15), season=self.temporada
        )

    def test_si_solo_juega_contra_tu_cadete_es_cadete(self):
        from .team_category_services import categoria_por_los_partidos

        self._partido(self.cadete, self.rival)

        self.assertEqual(categoria_por_los_partidos(self.rival), "CADETE")

    def test_si_juega_contra_dos_categorias_no_se_adivina(self):
        from .team_category_services import categoria_por_los_partidos

        self._partido(self.cadete, self.rival)
        self._partido(self.rival, self.senior)

        self.assertEqual(categoria_por_los_partidos(self.rival), "")

    def test_sin_partidos_no_dice_nada(self):
        from .team_category_services import categoria_por_los_partidos

        self.assertEqual(categoria_por_los_partidos(self.rival), "")
