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

    def test_calendar_page_renders_with_add_form(self):
        resp = self.client.get("/coach/partidos/", HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("Calendario de partidos", body)
        self.assertIn("Nuevo partido", body)
        self.assertIn("Guardar partido", body)  # el formulario de alta está en la propia página

    def test_calendar_filters_by_season(self):
        today = timezone.localdate()
        # Sin grupo para que no aparezcan en el datalist del formulario (que lista equipos del grupo);
        # así las aserciones miran solo el LISTADO de partidos.
        rival = Team.objects.create(name="Rival Actual", slug="ra")
        old_season = Season.objects.create(competition=self.comp, name="2024/2025", is_current=False)
        old_rival = Team.objects.create(name="Rival Viejo", slug="rv")
        Match.objects.create(
            season=self.season, home_team=self.team, away_team=rival,
            date=today, context=Match.CONTEXT_LEAGUE,
        )
        Match.objects.create(
            season=old_season, home_team=self.team, away_team=old_rival,
            date=datetime.date(2025, 1, 15), context=Match.CONTEXT_LEAGUE,
        )
        # Por defecto: solo la temporada actual.
        body = self.client.get("/coach/partidos/", HTTP_HOST="localhost").content.decode("utf-8")
        self.assertIn("Rival Actual", body)
        self.assertNotIn("Rival Viejo", body)
        # ?season=all -> todas.
        body_all = self.client.get("/coach/partidos/?season=all", HTTP_HOST="localhost").content.decode("utf-8")
        self.assertIn("Rival Actual", body_all)
        self.assertIn("Rival Viejo", body_all)

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

    def test_create_from_calendar_returns_to_calendar(self):
        """Al dar de alta desde el Calendario (next=/coach/partidos/), vuelve al Calendario."""
        today = timezone.localdate()
        resp = self.client.post(
            "/partido/crear/",
            {
                "opponent": "C.F. Calendario",
                "context": Match.CONTEXT_FRIENDLY,
                "home_away": "home",
                "date": (today + datetime.timedelta(days=4)).strftime("%Y-%m-%d"),
                "next": "/coach/partidos/",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/coach/partidos/"))
        self.assertTrue(Team.objects.filter(name_key=normalize_team_name_key("C.F. Calendario")).exists())
