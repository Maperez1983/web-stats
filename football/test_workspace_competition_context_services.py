from django.test import TestCase

from football import workspace_competition_context_services
from football.models import Competition, Group, Season, Team, Workspace, WorkspaceCompetitionContext


class WorkspaceCompetitionContextServicesTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Contexto', slug='liga-contexto')
        self.season = Season.objects.create(competition=competition, name='2026/2027')
        self.group = Group.objects.create(season=self.season, name='Grupo Contexto', slug='grupo-contexto')
        self.team = Team.objects.create(name='Equipo Contexto', slug='equipo-contexto', group=self.group)
        self.workspace = Workspace.objects.create(
            name='Cliente Contexto',
            slug='cliente-contexto',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )

    def test_bootstrap_creates_context_for_club_workspace(self):
        context = workspace_competition_context_services.bootstrap_workspace_competition_context(
            self.workspace,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name='Equipo Universo',
            auto_sync_enabled=False,
        )

        self.assertEqual(context.workspace, self.workspace)
        self.assertEqual(context.team, self.team)
        self.assertEqual(context.group, self.group)
        self.assertEqual(context.season, self.season)
        self.assertEqual(context.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
        self.assertEqual(context.external_group_key, '45030656')
        self.assertEqual(context.external_team_name, 'Equipo Universo')
        self.assertFalse(context.is_auto_sync_enabled)

    def test_bootstrap_updates_existing_context_metadata(self):
        context = workspace_competition_context_services.bootstrap_workspace_competition_context(self.workspace)

        updated = workspace_competition_context_services.bootstrap_workspace_competition_context(
            self.workspace,
            provider=WorkspaceCompetitionContext.PROVIDER_RFAF,
            external_competition_key='comp-1',
            external_group_key='group-1',
            external_team_key='team-1',
            external_source_url='https://example.com/group-1',
            auto_sync_enabled=False,
        )

        self.assertEqual(updated.pk, context.pk)
        self.assertEqual(updated.provider, WorkspaceCompetitionContext.PROVIDER_RFAF)
        self.assertEqual(updated.external_competition_key, 'comp-1')
        self.assertEqual(updated.external_group_key, 'group-1')
        self.assertEqual(updated.external_team_key, 'team-1')
        self.assertEqual(updated.external_source_url, 'https://example.com/group-1')
        self.assertFalse(updated.is_auto_sync_enabled)

    def test_bootstrap_ignores_non_club_workspace(self):
        workspace = Workspace.objects.create(
            name='Task Studio',
            slug='task-studio-contexto',
            kind=Workspace.KIND_TASK_STUDIO,
        )

        context = workspace_competition_context_services.bootstrap_workspace_competition_context(workspace)

        self.assertIsNone(context)
