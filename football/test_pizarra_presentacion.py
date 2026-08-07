"""Con qué se dibuja cada jugador en una pizarra: chapa, camiseta, foto o avatar.

Antes de esto, de las cuatro pizarras interactivas SÓLO el 11 inicial dejaba elegir, y lo
guardaba en el `localStorage` del navegador: la elección no le seguía ni a la pantalla de al lado
ni al iPad del campo. La pizarra de plantilla y el Planteamiento no ofrecían nada.

Ahora hay una puerta única en el servidor (`resolve_player_board_token_url`), la preferencia vive
por equipo, y las pizarras comparten el mismo include de selectores.
"""
import datetime

from django.test import SimpleTestCase, TestCase

from football.models import Player, Team

HOY = datetime.date(2026, 8, 7)


def _nacido_con(anios):
    return HOY.replace(year=HOY.year - anios) - datetime.timedelta(days=40)


class ConQueSeDibujaCadaFichaTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Estilos", slug="estilos", category="Senior")
        self.campo = Player.objects.create(
            team=self.team, name="Campo", number=5, position="Defensa",
            birth_date=_nacido_con(24), has_federative_license=True, is_active=True,
        )
        self.portero = Player.objects.create(
            team=self.team, name="Portero", number=1, position="Portero",
            birth_date=_nacido_con(24), has_federative_license=True, is_active=True,
        )

    def _url(self, player, kit, estilo):
        from football.views import resolve_player_board_token_url

        return resolve_player_board_token_url(player, kit=kit, estilo=estilo)

    def test_los_cuatro_estilos_son_los_del_11(self):
        """Las palabras las estrenó el 11 inicial; si aquí cambiaran, la misma cosa tendría dos
        nombres según la pantalla."""
        from football.views import board_estilo_opciones

        self.assertEqual(
            [c for c, _ in board_estilo_opciones()], ["chapa", "camiseta", "foto", "avatar"]
        )

    def test_la_chapa_sigue_a_la_equipacion_y_el_portero_lleva_la_suya(self):
        esperado = {
            "titular": ("chapa_local.png", "chapa_gk_azul.png"),
            "visitante": ("chapa_away.png", "chapa_gk_negra.png"),
            "turquesa": ("chapa_turquesa.png", "chapa_gk_magenta.png"),
            "blanca": ("chapa_blanca.png", "chapa_gk_azul.png"),
        }
        for kit, (campo, gk) in esperado.items():
            with self.subTest(kit=kit):
                self.assertTrue(self._url(self.campo, kit, "chapa").endswith(campo))
                self.assertTrue(self._url(self.portero, kit, "chapa").endswith(gk))

    def test_la_camiseta_sigue_a_la_equipacion(self):
        esperado = {
            "titular": ("kit_1a_rayas_anchas.png", "kit_portero_azul.png"),
            "visitante": ("kit_2a_amarilla.png", "kit_portero_negra.png"),
            "turquesa": ("kit_entreno_turquesa.png", "kit_portero_coral.png"),
            "blanca": ("kit_entreno_blanca.png", "kit_portero_azul.png"),
        }
        for kit, (campo, gk) in esperado.items():
            with self.subTest(kit=kit):
                self.assertTrue(self._url(self.campo, kit, "camiseta").endswith(campo))
                self.assertTrue(self._url(self.portero, kit, "camiseta").endswith(gk))

    def test_el_avatar_sigue_siendo_la_figura_por_equipacion(self):
        self.assertTrue(self._url(self.campo, "visitante", "avatar").endswith("kit_away_hd.png"))
        self.assertTrue(self._url(self.portero, "visitante", "avatar").endswith("gk_black_hd.png"))

    def test_sin_foto_el_estilo_foto_no_deja_la_ficha_vacia(self):
        """Cascada de respaldo, la misma que estrenó el 11: foto -> avatar -> chapa."""
        url = self._url(self.campo, "titular", "foto")
        self.assertTrue(url, "la ficha se ha quedado sin imagen")
        self.assertTrue(url.endswith("kit_home_hd.png"), url)

    def test_un_estilo_desconocido_no_rompe_la_pizarra(self):
        from football.views import board_estilo_valido

        self.assertEqual(board_estilo_valido("lo-que-sea"), "avatar")
        self.assertEqual(board_estilo_valido(None), "avatar")
        self.assertEqual(board_estilo_valido("CHAPA"), "chapa")

    def test_el_lesionado_y_el_a_prueba_conservan_su_figura_de_estado(self):
        """Se leen de un golpe de vista; una chapa no distingue a quien está de muletas."""
        from football.models import PlayerInjuryRecord
        from football.views import _build_coach_pitch_board_players

        lesionado = Player.objects.create(
            team=self.team, name="Lesionado", number=8, position="Defensa",
            birth_date=_nacido_con(24), has_federative_license=True, is_active=True,
        )
        prueba = Player.objects.create(
            team=self.team, name="A prueba", number=9, position="Delantero",
            birth_date=_nacido_con(24), has_federative_license=False, is_active=True,
        )
        PlayerInjuryRecord.objects.create(player=lesionado, injury_date=HOY, is_active=True, is_recovered=False)
        chips = {
            c["id"]: c
            for c in _build_coach_pitch_board_players(
                self.team, [lesionado, prueba], {}, {lesionado.id}, include_scouts=False, estilo="chapa"
            )
        }
        self.assertEqual(chips[lesionado.id]["avatar_url"], "")
        self.assertIn("injured_crutches", chips[lesionado.id]["avatar_static"])
        self.assertEqual(chips[prueba.id]["avatar_url"], "")
        self.assertIn("chandal", chips[prueba.id]["avatar_static"])


class LaPreferenciaViveEnElServidorTests(TestCase):
    def test_se_guarda_por_equipo_y_se_lee(self):
        from football.models import Workspace
        from football.views import (
            board_estilo_para_equipo, board_kit_para_equipo,
            guardar_board_estilo_para_equipo, guardar_board_kit_para_equipo,
        )

        equipo_a = Team.objects.create(name="A", slug="a")
        equipo_b = Team.objects.create(name="B", slug="b")
        ws = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, primary_team=equipo_a)

        self.assertEqual(board_estilo_para_equipo(ws, equipo_a), "avatar")
        guardar_board_estilo_para_equipo(ws, equipo_a, "chapa")
        guardar_board_kit_para_equipo(ws, equipo_a, "visitante")
        self.assertEqual(board_estilo_para_equipo(ws, equipo_a), "chapa")
        self.assertEqual(board_kit_para_equipo(ws, equipo_a), "visitante")
        # El de al lado no se entera: en un club de siete equipos no todos van igual el mismo día.
        self.assertEqual(board_estilo_para_equipo(ws, equipo_b), "avatar")
        self.assertEqual(board_kit_para_equipo(ws, equipo_b), "titular")

    def test_estilo_y_equipacion_conviven_en_la_misma_preferencia(self):
        """Son las dos mitades de una decisión; separarlas obligaría a leer dos veces."""
        from football.models import Workspace, WorkspacePreference
        from football.views import guardar_board_estilo_para_equipo, guardar_board_kit_para_equipo

        equipo = Team.objects.create(name="C", slug="c")
        ws = Workspace.objects.create(name="Club C", kind=Workspace.KIND_CLUB, primary_team=equipo)
        guardar_board_kit_para_equipo(ws, equipo, "turquesa")
        guardar_board_estilo_para_equipo(ws, equipo, "camiseta")
        self.assertEqual(WorkspacePreference.objects.filter(workspace=ws).count(), 1)


class LasPizarrasNoVuelvenADivergirTests(SimpleTestCase):
    """Cada pizarra interactiva de jugadores ofrece el MISMO selector, por el mismo include."""

    PIZARRAS = (
        "_coach_pitch_board.html",   # plantilla: la incluyen cinco pantallas
        "tactical_plan.html",        # planteamiento
    )

    def test_incluyen_el_partial_compartido(self):
        from pathlib import Path

        base = Path(__file__).resolve().parent / "templates" / "football"
        for nombre in self.PIZARRAS:
            with self.subTest(pizarra=nombre):
                html = (base / nombre).read_text(encoding="utf-8")
                self.assertIn(
                    "includes/_board_view_controls.html", html,
                    "esta pizarra se ha quedado sin el selector compartido",
                )

    def test_el_11_arranca_de_la_preferencia_del_servidor(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parent / "templates" / "football" / "coach_initial_eleven.html"
        ).read_text(encoding="utf-8")
        self.assertIn("TOKEN_STYLE_SERVIDOR", html)
        self.assertIn("if (TOKEN_STYLE_SERVIDOR) return TOKEN_STYLE_SERVIDOR;", html)
        self.assertIn("estilo=", html, "el 11 no devuelve su elección al servidor")

    def test_la_pizarra_de_ojeo_NO_lo_lleva_a_proposito(self):
        """Pinta ojeados, que no son jugadores tuyos ni visten tu equipación."""
        from pathlib import Path

        html = (
            Path(__file__).resolve().parent / "templates" / "football" / "_scouting_pitch_board.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("includes/_board_view_controls.html", html)
