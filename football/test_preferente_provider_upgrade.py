from django.test import TestCase

from football.models import Team, Workspace, WorkspaceCompetitionContext
from football.workspace_competition_context_services import bootstrap_workspace_competition_context


class PreferenteProviderUpgradeTests(TestCase):
    """Un equipo con URL de La Preferente no debe quedarse con el contexto en 'manual'.

    Si se queda en 'manual', el sync no baja su clasificación y la home ignora el snapshot.
    """

    def test_manual_with_preferente_url_becomes_preferente(self):
        team = Team.objects.create(
            name="CD Benagalbon",
            slug="cd-bena",
            is_primary=True,
            preferente_url="https://www.lapreferente.com/E147C22273-1/cd-benagalbon",
        )
        workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=team
        )
        ctx = bootstrap_workspace_competition_context(workspace, primary_team=team)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_PREFERENTE)
        self.assertTrue(ctx.external_source_url.endswith("cd-benagalbon"))

    def test_team_without_preferente_url_stays_manual(self):
        team = Team.objects.create(name="X", slug="x", is_primary=True)
        workspace = Workspace.objects.create(
            name="X", slug="xw", kind=Workspace.KIND_CLUB, primary_team=team
        )
        ctx = bootstrap_workspace_competition_context(workspace, primary_team=team)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_MANUAL)

    def test_universo_context_is_not_overridden(self):
        team = Team.objects.create(
            name="Y", slug="y", is_primary=True, preferente_url="https://www.lapreferente.com/x"
        )
        workspace = Workspace.objects.create(
            name="Y", slug="yw", kind=Workspace.KIND_CLUB, primary_team=team
        )
        ctx = bootstrap_workspace_competition_context(
            workspace,
            primary_team=team,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key="999",
        )
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
