from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import (
    Player,
    PlayerCommunication,
    PlayerEvaluation,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class PortalDeFamiliaTests(TestCase):
    """Cuando detrás de la cuenta está la familia, el portal no le atribuye actos al jugador."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno4", password="x")
        self.workspace = Workspace.objects.create(
            name="Club familia", slug="club-familia", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Benjamin fam", slug="benjamin-fam")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.madre = User.objects.create_user(username="madre", password="x")
        self.player = Player.objects.create(
            name="Niño Uno",
            team=self.team,
            is_active=True,
            user=self.madre,
            user_is_guardian=True,
            contact_is_guardian=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.madre, role=WorkspaceMembership.ROLE_VIEWER
        )
        self.client.force_login(self.madre)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def test_la_familia_no_puede_autovalorar_al_jugador(self):
        resp = self.client.post(
            reverse("player-home"),
            {"form_action": "self_assessment", "technical_rating": "9"},
            follow=True,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            PlayerEvaluation.objects.filter(player=self.player, author_kind=PlayerEvaluation.AUTHOR_SELF).exists()
        )

    def test_el_portal_dice_que_entras_como_familia(self):
        resp = self.client.get(reverse("player-home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "como familia de")

    def test_el_jugador_si_puede_autovalorarse(self):
        self.player.user_is_guardian = False
        self.player.save(update_fields=["user_is_guardian"])

        self.client.post(
            reverse("player-home"),
            {"form_action": "self_assessment", "technical_rating": "7"},
            follow=True,
        )

        self.assertTrue(
            PlayerEvaluation.objects.filter(player=self.player, author_kind=PlayerEvaluation.AUTHOR_SELF).exists()
        )


class PublicacionDeComunicacionesTests(TestCase):
    """Nada llega al portal por existir: llega porque alguien lo publica."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno5", password="x")
        self.workspace = Workspace.objects.create(
            name="Club publica", slug="club-publica", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Cadete pub", slug="cadete-pub")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.jugador_user = User.objects.create_user(username="jugador5", password="x")
        self.player = Player.objects.create(
            name="Jugador Pub", team=self.team, is_active=True, user=self.jugador_user
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.jugador_user, role=WorkspaceMembership.ROLE_VIEWER
        )
        self.interna = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_INTERNAL,
            message="Hablar con su padre sobre la actitud",
        )
        self.medica = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_MEDICAL,
            message="Sospecha de rotura, pendiente de prueba",
        )

    def _portal(self):
        self.client.force_login(self.jugador_user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()
        return self.client.get(reverse("player-home"))

    def test_lo_interno_y_lo_medico_no_salen_solos(self):
        resp = self._portal()

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Hablar con su padre")
        self.assertNotContains(resp, "Sospecha de rotura")

    def test_publicar_una_concreta_la_hace_visible(self):
        self.interna.published_to_player = True
        self.interna.save(update_fields=["published_to_player"])

        resp = self._portal()

        self.assertContains(resp, "Hablar con su padre")
        # La otra sigue siendo del staff.
        self.assertNotContains(resp, "Sospecha de rotura")

    def test_el_staff_publica_y_despublica_desde_la_ficha(self):
        staff = User.objects.create_user(username="staff5", password="x")
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
            {"form_action": "communication_publish", "communication_id": self.interna.id, "publish": "1"},
        )
        self.interna.refresh_from_db()
        self.assertTrue(self.interna.published_to_player)
        self.assertIsNotNone(self.interna.published_to_player_at)

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "communication_publish", "communication_id": self.interna.id, "publish": "0"},
        )
        self.interna.refresh_from_db()
        self.assertFalse(self.interna.published_to_player)
