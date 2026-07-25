import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from football.models import (
    Competition,
    Group,
    Match,
    Player,
    Season,
    Team,
    TeamRosterSnapshot,
    Workspace,
    WorkspaceMembership,
)


class NextMatchReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.comp = Competition.objects.create(name="DH", slug="dh")
        self.season = Season.objects.create(competition=self.comp, name="2026/2027", is_current=True)
        self.group = Group.objects.create(season=self.season, name="G", slug="g")
        self.team = Team.objects.create(name="C.D. Ejemplo", slug="cde", is_primary=True, group=self.group)
        self.workspace = Workspace.objects.create(
            name="C.D. Ejemplo", slug="cde", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _get(self):
        return self.client.get("/coach/partido/informe/", HTTP_HOST="localhost")

    def test_empty_state_without_match(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("No hay un próximo partido", resp.content.decode("utf-8"))

    def test_renders_with_match_and_h2h(self):
        rival = Team.objects.create(name="C.D. Rival", slug="rival", group=self.group)
        today = timezone.localdate()
        # Próximo partido (futuro) y un enfrentamiento pasado con resultado.
        Match.objects.create(
            season=self.season, home_team=self.team, away_team=rival,
            date=today + datetime.timedelta(days=7), context=Match.CONTEXT_LEAGUE,
        )
        Match.objects.create(
            season=self.season, home_team=self.team, away_team=rival,
            date=today - datetime.timedelta(days=30), home_score=2, away_score=1,
            context=Match.CONTEXT_LEAGUE,
        )
        TeamRosterSnapshot.objects.create(
            team=rival,
            roster_payload=[
                {"name": "Portero R", "number": 1, "position": "Portero"},
                {"name": "Lat D", "number": 2, "position": "Lateral derecho"},
                {"name": "Central A", "number": 4, "position": "Central"},
                {"name": "Central B", "number": 5, "position": "Central"},
                {"name": "Lat I", "number": 3, "position": "Lateral izquierdo"},
                {"name": "Pivote R", "number": 6, "position": "Pivote"},
                {"name": "Int D", "number": 8, "position": "Interior derecho"},
                {"name": "Int I", "number": 10, "position": "Interior izquierdo"},
                {"name": "Ext D", "number": 7, "position": "Extremo derecho"},
                {"name": "Delantero R", "number": 9, "position": "Delantero"},
                {"name": "Ext I", "number": 11, "position": "Extremo izquierdo"},
            ],
        )
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        # No debe romperse; el informe debe montar y no ser el estado vacío.
        self.assertNotIn("No hay un próximo partido", body)
        self.assertIn("C.D. Rival", body)
        self.assertIn("Historial contra", body)
        self.assertIn("2–1", body)  # resultado del enfrentamiento previo
