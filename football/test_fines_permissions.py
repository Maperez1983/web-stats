from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import Player, PlayerFine, Team, Workspace, WorkspaceMembership


class FinesPermissionTests(TestCase):
    """Registrar multas dejó de ser exclusivo de administradores: un gestor del club
    (owner/admin del workspace) también puede, para que el informe de microciclo se rellene
    aunque el entrenador no sea administrador de plataforma."""

    def setUp(self):
        # Usuario normal (NO superuser/admin de plataforma), dueño del workspace.
        self.user = get_user_model().objects.create_user("coach", "coach@example.com", "x")
        self.team = Team.objects.create(name="C.D. Prueba", slug="cdp", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="C.D. Prueba", slug="cdp", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER
        )
        self.player = Player.objects.create(team=self.team, name="Bea Dos", number=2, is_active=True)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def test_non_admin_owner_can_register_fine(self):
        resp = self.client.post(
            "/coach/multas/",
            {"form_action": "add", "player_id": self.player.id, "reason": "absence", "amount": 10, "note": "Falta"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PlayerFine.objects.filter(player=self.player).count(), 1)
        fine = PlayerFine.objects.get(player=self.player)
        self.assertEqual(fine.amount, 10)
        self.assertEqual(fine.reason, PlayerFine.REASON_ABSENCE)
