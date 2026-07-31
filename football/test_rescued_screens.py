"""
Dos pantallas que existían y nadie podía alcanzar.

`/player/N/informe/editar/` (34 campos) y `/player/N/evolucion/pdf/` funcionaban, pero ni una
plantilla ni una vista las enlazaba: se llegaba sólo escribiendo la URL a mano. Y
`/player/N/presentacion/` redirigía a `?preview=player`, un modo que ya no existe.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse

from football.models import Player, Team, Workspace, WorkspaceTeam


class RescuedScreensTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
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

    def test_ficha_links_the_season_report(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-season-report-edit", args=[self.player.id]))

    def test_ficha_links_the_evolution_pdf(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-evolution-pdf", args=[self.player.id]))

    def test_the_dead_presentation_route_is_gone(self):
        # Redirigía a `?preview=player`, un modo retirado: no llevaba a ninguna parte.
        with self.assertRaises(NoReverseMatch):
            reverse("player-presentation", args=[self.player.id])
