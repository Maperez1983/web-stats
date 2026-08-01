from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import player_portal_policy as policy
from .models import (
    Player,
    PlayerInjuryRecord,
    PlayerPortalPolicy,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class ParteMedicoPublicadoTests(TestCase):
    """Con la sección en 'sólo lo publicado', el parte es del staff hasta que se publica."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno7", password="x")
        self.workspace = Workspace.objects.create(
            name="Club medico", slug="club-medico", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Cadete med", slug="cadete-med")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.jugador_user = User.objects.create_user(username="jugador7", password="x")
        self.player = Player.objects.create(
            name="Jugador Med", team=self.team, is_active=True, user=self.jugador_user, injury="Molestias"
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.jugador_user, role=WorkspaceMembership.ROLE_VIEWER
        )
        self.parte = PlayerInjuryRecord.objects.create(
            player=self.player,
            injury="Rotura fibrilar isquios",
            injury_date="2026-07-01",
        )

    def _portal(self):
        self.client.force_login(self.jugador_user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()
        return self.client.get(reverse("player-home"))

    def _politica_solo_publicado(self):
        PlayerPortalPolicy.objects.update_or_create(
            workspace=self.workspace,
            team=None,
            defaults={"sections": {"injuries": policy.PUBLISHED_ONLY}},
        )

    def test_la_seccion_admite_solo_lo_publicado(self):
        seccion = next(s for s in policy.SECTIONS if s["key"] == "injuries")

        self.assertIn(policy.PUBLISHED_ONLY, seccion["states"])
        # El default no cambia: quien no toque nada sigue viéndolo como siempre.
        self.assertEqual(seccion["default"], policy.VISIBLE)

    def test_sin_publicar_no_se_ve_el_parte(self):
        self._politica_solo_publicado()

        resp = self._portal()

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Rotura fibrilar")
        # Y tampoco se cuela por la puerta de atrás del campo suelto del jugador.
        self.assertNotContains(resp, "Molestias")

    def test_publicado_si_se_ve(self):
        self._politica_solo_publicado()
        self.parte.published_to_player = True
        self.parte.save(update_fields=["published_to_player"])

        resp = self._portal()

        self.assertContains(resp, "Rotura fibrilar")

    def test_con_la_politica_de_siempre_no_cambia_nada(self):
        resp = self._portal()

        self.assertContains(resp, "Rotura fibrilar")

    def test_el_staff_publica_desde_la_ficha(self):
        staff = User.objects.create_user(username="staff7", password="x")
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=staff, role=WorkspaceMembership.ROLE_ADMIN
        )
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "injury_publish", "injury_id": self.parte.id},
        )
        self.parte.refresh_from_db()
        self.assertTrue(self.parte.published_to_player)
        self.assertIsNotNone(self.parte.published_to_player_at)

        # El mismo botón lo retira.
        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "injury_publish", "injury_id": self.parte.id},
        )
        self.parte.refresh_from_db()
        self.assertFalse(self.parte.published_to_player)
