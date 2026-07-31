"""
La ficha con lesiones renderiza, y cada lesión enlaza con su ficha.

INCIDENTE: añadí una `@property detail_url` al modelo sin comprobar que la VISTA ya asignaba
ese atributo a cada registro. Una property es de sólo lectura, así que la asignación reventó
con `AttributeError: can't set attribute` y la ficha entera devolvió 500 en producción.
Ningún test lo cogió porque los que había no creaban lesiones.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import (
    Player, PlayerInjuryRecord, Team, Workspace, WorkspaceTeam,
)


class FichaWithInjuriesTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Acosta", is_active=True)
        self.record = PlayerInjuryRecord.objects.create(
            player=self.player, injury="Rotura fibrilar", injury_date=date(2026, 7, 28)
        )
        self.workspace = Workspace.objects.create(
            name="Club", kind=Workspace.KIND_CLUB, is_active=True
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace.owner_user = staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_ficha_renders_with_injuries(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)

    def test_each_injury_links_to_its_detail(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(
            response, reverse("player-injury-detail", args=[self.player.id, self.record.id])
        )
