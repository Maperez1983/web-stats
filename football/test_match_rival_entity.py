import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from football.models import (
    Competition,
    Group,
    Match,
    Season,
    Team,
    Workspace,
    WorkspaceMembership,
    normalize_team_name_key,
)


class MatchRivalEntityTests(TestCase):
    """Al fijar un partido, el rival debe crearse como Team con entidad propia y SIN duplicar:
    dos variantes del mismo nombre ('C.D. Rival' == 'CD Rival') deben reutilizar el mismo equipo
    (vía resolve_or_create_team / name_key)."""

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

    def _create_match(self, opponent, date):
        return self.client.post(
            "/coach/agenda/",
            {
                "agenda_action": "create_match",
                "agenda_match_opponent": opponent,
                "agenda_match_date": date.strftime("%Y-%m-%d"),
                "agenda_match_context": Match.CONTEXT_FRIENDLY,
                "agenda_match_home_away": "home",
            },
            HTTP_HOST="localhost",
        )

    def test_rival_created_as_entity_and_deduped(self):
        today = timezone.localdate()
        key = normalize_team_name_key("C.D. Rival")

        self._create_match("C.D. Rival", today + datetime.timedelta(days=2))
        rivals = Team.objects.filter(name_key=key).exclude(id=self.team.id)
        self.assertEqual(rivals.count(), 1)  # se creó como entidad propia
        rival = rivals.first()
        self.assertTrue(rival.id)  # tiene id
        self.assertEqual(rival.name_key, key)

        # Segundo partido con el nombre en otra grafía -> NO debe duplicar el rival.
        self._create_match("CD Rival", today + datetime.timedelta(days=9))
        self.assertEqual(Team.objects.filter(name_key=key).exclude(id=self.team.id).count(), 1)
        # Pero sí deben existir dos partidos contra ese rival.
        self.assertEqual(
            Match.objects.filter(home_team=self.team, away_team=rival).count(), 2
        )

    def test_match_hub_modal_create_dedups_rival(self):
        """El modal 'Nuevo partido' (match-hub-create) también deduplica el rival al escribirlo."""
        today = timezone.localdate()
        key = normalize_team_name_key("U.D. Nueva")

        def _create(opponent, date):
            return self.client.post(
                "/partido/crear/",
                {
                    "opponent": opponent,
                    "context": Match.CONTEXT_FRIENDLY,
                    "home_away": "home",
                    "date": date.strftime("%Y-%m-%d"),
                },
                HTTP_HOST="localhost",
            )

        _create("U.D. Nueva", today + datetime.timedelta(days=3))
        self.assertEqual(Team.objects.filter(name_key=key).count(), 1)
        _create("UD Nueva", today + datetime.timedelta(days=10))
        self.assertEqual(Team.objects.filter(name_key=key).count(), 1)
