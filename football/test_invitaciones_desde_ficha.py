from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Player,
    Team,
    UserInvitation,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class InvitacionesDesdeLaFichaTests(TestCase):
    """
    El acceso se da desde donde vive la persona: staff en su ficha, jugadores en la
    plantilla. La lista de miembros sólo reparte accesos de directiva/administración.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="dueno2", password="x", email="d@club.com")
        self.workspace = Workspace.objects.create(
            name="Club invitaciones",
            slug="club-invitaciones",
            kind=Workspace.KIND_CLUB,
            owner_user=self.owner,
        )
        self.team = Team.objects.create(name="Cadete inv", slug="cadete-inv")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.player = Player.objects.create(name="Jugador Inv", team=self.team, is_active=True)
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_miembros_no_invita_entrenadores(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "entrenador@club.com", "role_preset": "entrenador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="entrenador@club.com").exists())
        self.assertContains(resp, "ficha de staff")

    def test_miembros_no_invita_jugadores(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "jugador@club.com", "role_preset": "jugador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="jugador@club.com").exists())

    def test_miembros_si_invita_a_directiva(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "tesorero@club.com", "name": "Tesorero", "role_preset": "administrador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(email="tesorero@club.com").exists())

    def test_el_jugador_se_invita_desde_la_plantilla(self):
        resp = self.client.post(
            reverse("player-portal-settings"),
            {
                "action": "invite_player",
                "player_id": self.player.id,
                "player_email": "madre@casa.com",
            },
        )

        self.assertEqual(resp.status_code, 200)
        invitado = User.objects.filter(email="madre@casa.com").first()
        self.assertIsNotNone(invitado)
        # La invitación viaja atada a la ficha del jugador, no se adivina luego por el nombre.
        self.assertTrue(
            UserInvitation.objects.filter(user=invitado, player=self.player, is_active=True).exists()
        )

    def test_invitar_jugador_sin_email_no_crea_nada(self):
        antes = User.objects.count()

        resp = self.client.post(
            reverse("player-portal-settings"),
            {"action": "invite_player", "player_id": self.player.id, "player_email": ""},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), antes)
