from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import Team, Workspace, WorkspaceCompetitionContext, WorkspaceMembership


class CompetitionAutolinkOnboardingTests(TestCase):
    """La acción 'autolink' del onboarding engancha la liga de un clic.

    Universo (server-side) cuando hay una única coincidencia; si no, cae a La Preferente;
    y si hay varias coincidencias en Universo, las ofrece para elegir a mano.
    """

    BASE = {"workspace_name": "Bena", "team_name": "CD Benagalbon"}

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("ol", "ol@example.com", "x")
        self.team = Team.objects.create(name="CD Benagalbon", slug="cd-bena", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        try:
            WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        except Exception:
            pass
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _post_autolink(self):
        return self.client.post("/onboarding/", {**self.BASE, "action": "autolink"}, HTTP_HOST="localhost")

    def test_universo_single_match_binds_and_syncs(self):
        candidate = [{
            "external_competition_key": "C1",
            "external_group_key": "45030656",
            "external_team_key": "T9",
            "external_team_name": "CD Benagalbón",
            "team_name": "CD Benagalbón",
            "competition_name": "2ª Andaluza",
            "group_name": "Grupo X",
            "season_name": "2026/2027",
        }]
        with mock.patch("football.views._search_universo_competition_candidates", return_value=candidate), \
             mock.patch("football.views._ensure_universo_group_models_from_candidate", return_value=None), \
             mock.patch("football.views._sync_workspace_competition_context", return_value=(None, "")):
            self._post_autolink()
        ctx = WorkspaceCompetitionContext.objects.filter(workspace=self.workspace, team=self.team).first()
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
        self.assertEqual(ctx.external_group_key, "45030656")

    def test_preferente_fallback_when_no_universo_match(self):
        with mock.patch("football.views._search_universo_competition_candidates", return_value=[]), \
             mock.patch("football.views.find_preferente_team_url", return_value="https://www.lapreferente.com/?IDequipo=99"):
            self._post_autolink()
        self.team.refresh_from_db()
        self.assertTrue(self.team.preferente_url.endswith("IDequipo=99"))

    def test_ambiguous_universo_offers_choice(self):
        candidates = [
            {"external_group_key": "1", "external_team_key": "a", "team_name": "A"},
            {"external_group_key": "2", "external_team_key": "b", "team_name": "B"},
        ]
        with mock.patch("football.views._search_universo_competition_candidates", return_value=candidates):
            resp = self._post_autolink()
        self.assertIn("coincidencias en Universo", resp.content.decode("utf-8", "ignore"))

    def test_unmatched_shows_helpful_error(self):
        with mock.patch("football.views._search_universo_competition_candidates", return_value=[]), \
             mock.patch("football.views.find_preferente_team_url", return_value=""):
            resp = self._post_autolink()
        body = resp.content.decode("utf-8", "ignore")
        self.assertIn("No pudimos detectar la liga", body)
