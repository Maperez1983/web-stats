from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import (
    Competition,
    Group,
    Season,
    Match,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)
from .views import build_match_rival_picker_options


def _temporada_de_pruebas(sufijo):
    competicion = Competition.objects.create(name=f"Competición {sufijo}", slug=f"comp-{sufijo}")
    return Season.objects.create(competition=competicion, name=f"2026/2027 {sufijo}")


class SelectorDeRivalTests(TestCase):
    """La lista de rivales del alta deja de esconder a los de fuera de tu grupo."""

    def setUp(self):
        cache.clear()
        temporada = _temporada_de_pruebas("alta-a")
        self.grupo = Group.objects.create(name="Div. Honor Gr.2", season=temporada, slug="dh2-alta")
        self.otro_grupo = Group.objects.create(name="Cadete Gr.1", season=temporada, slug="cad1-alta")
        self.propio = Team.objects.create(name="Benagalbón", slug="bena-alta", group=self.grupo)
        self.de_mi_liga = Team.objects.create(
            name="ALHAURIN DE LA TORRE C.F.", slug="alhaurin-alta", group=self.grupo
        )
        self.de_otra_liga = Team.objects.create(
            name="C.D. Rincón de la Victoria", slug="rincon-alta", group=self.otro_grupo
        )
        self.sin_grupo = Team.objects.create(name="Torremoya", slug="torremoya-alta")

    def test_estan_todos_no_solo_los_de_mi_grupo(self):
        nombres = [o["name"] for o in build_match_rival_picker_options(self.propio)]

        self.assertIn("ALHAURIN DE LA TORRE C.F.", nombres)
        self.assertIn("C.D. Rincón de la Victoria", nombres)
        self.assertIn("Torremoya", nombres)
        self.assertNotIn("Benagalbón", nombres)

    def test_los_de_mi_liga_van_primero(self):
        opciones = build_match_rival_picker_options(self.propio)

        self.assertEqual(opciones[0]["name"], "ALHAURIN DE LA TORRE C.F.")
        self.assertTrue(opciones[0]["same_group"])

    def test_cada_opcion_lleva_id_y_pista_para_distinguir(self):
        opciones = {o["name"]: o for o in build_match_rival_picker_options(self.propio)}

        self.assertEqual(opciones["C.D. Rincón de la Victoria"]["id"], self.de_otra_liga.id)
        self.assertIn("Cadete Gr.1", opciones["C.D. Rincón de la Victoria"]["hint"])


class AltaDePartidoReutilizaElEquipoTests(TestCase):
    """Crear el amistoso con el id NO duplica; y el nombre exacto tampoco."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno13", password="x")
        self.workspace = Workspace.objects.create(
            name="Club alta", slug="club-alta", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.grupo = Group.objects.create(
            name="Grupo alta", season=_temporada_de_pruebas("alta-b"), slug="grupo-alta"
        )
        self.propio = Team.objects.create(name="Mi Equipo", slug="mi-equipo-alta", group=self.grupo)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.propio, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.rival = Team.objects.create(name="ALHAURIN DE LA TORRE C.F.", slug="alh-alta")
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.propio.id)}
        session.save()

    def _crear(self, **extra):
        datos = {"team": self.propio.id, "context": "friendly", "date": "2026-08-15"}
        datos.update(extra)
        return self.client.post(reverse("match-hub-create"), datos)

    def test_con_id_reutiliza_el_equipo(self):
        antes = Team.objects.count()

        self._crear(opponent_team_id=self.rival.id, opponent="ALHAURIN DE LA TORRE C.F.")

        self.assertEqual(Team.objects.count(), antes)
        self.assertTrue(Match.objects.filter(away_team=self.rival).exists())

    def test_el_nombre_exacto_tampoco_duplica(self):
        antes = Team.objects.count()

        self._crear(opponent="ALHAURIN DE LA TORRE C.F.")

        self.assertEqual(Team.objects.count(), antes)

    def test_escribirlo_distinto_si_crea_uno_nuevo(self):
        """Por eso el selector avisa antes: la clave no quita sufijos, y son claves distintas."""
        antes = Team.objects.count()

        self._crear(opponent="Alhaurín Torre")

        self.assertEqual(Team.objects.count(), antes + 1)

    def test_el_rival_de_amistoso_no_entra_en_el_grupo_de_mi_liga(self):
        self._crear(opponent="Equipo Nuevo De Amistoso")

        nuevo = Team.objects.get(name="Equipo Nuevo De Amistoso")
        self.assertIsNone(nuevo.group_id)
