from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from football.models import Team, Workspace, WorkspaceCompetitionContext, WorkspaceTeam


class AutolinkCommandFlagsTests(TestCase):
    """`autolink_competition_contexts --only-preferente --senior-only`.

    El pase de senior desde IP residencial: solo toca La Preferente y solo equipos senior.
    """

    def setUp(self):
        self.senior = Team.objects.create(name="CD Bena", slug="cd-bena", is_primary=True, category="Senior")
        self.youth = Team.objects.create(name="CD Bena Cadete", slug="cd-bena-cad", category="Cadete")
        self.workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=self.senior, is_active=True
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.youth)

    def test_only_preferente_senior_only_targets_senior(self):
        queried = []

        def fake_find(name):
            queried.append(name)
            return "https://www.lapreferente.com/?IDequipo=7"

        with mock.patch("football.services.find_preferente_team_url", side_effect=fake_find):
            call_command(
                "autolink_competition_contexts",
                "--only-preferente",
                "--senior-only",
                "--commit",
                stdout=StringIO(),
            )

        # Solo el senior se consulta en La Preferente (el cadete queda fuera del filtro).
        self.assertEqual(queried, ["CD Bena"])
        self.senior.refresh_from_db()
        self.assertTrue(self.senior.preferente_url.endswith("IDequipo=7"))
        ctx = WorkspaceCompetitionContext.objects.filter(team=self.senior).first()
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_PREFERENTE)
        # El equipo de cantera no se toca.
        self.youth.refresh_from_db()
        self.assertFalse(self.youth.preferente_url)

    def test_only_preferente_does_not_call_universo(self):
        # Con --only-preferente no debe intentarse la búsqueda en Universo.
        with mock.patch("football.services.find_preferente_team_url", return_value=""), \
             mock.patch("football.views._search_universo_competition_candidates") as universo:
            call_command(
                "autolink_competition_contexts",
                "--only-preferente",
                "--senior-only",
                stdout=StringIO(),
            )
        universo.assert_not_called()
