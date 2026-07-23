from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from football.models import Team, Workspace, WorkspaceCompetitionContext, WorkspaceTeam


class AutolinkCompetitionContextsTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='C.D. Benagalbón', slug='cd-benagalbon', is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Benagalbón', slug='benagalbon', kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

    def _run(self, universo=None, preferente_url='', **kwargs):
        out = StringIO()
        with mock.patch('football.views._search_universo_competition_candidates', return_value=universo or []), \
             mock.patch('football.services.find_preferente_team_url', return_value=preferente_url):
            call_command('autolink_competition_contexts', stdout=out, **kwargs)
        return out.getvalue()

    def test_report_mode_does_not_write(self):
        self._run(universo=[{'external_group_key': 'g1', 'external_team_key': 't1', 'team_name': 'C.D. Benagalbón'}])
        self.assertEqual(WorkspaceCompetitionContext.objects.count(), 0)

    def test_commit_links_universo_single_match(self):
        out = self._run(
            universo=[{'external_group_key': 'g1', 'external_team_key': 't1',
                       'external_competition_key': 'c1', 'team_name': 'C.D. Benagalbón'}],
            commit=True,
        )
        ctx = WorkspaceCompetitionContext.objects.get(workspace=self.workspace, team=self.team)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
        self.assertEqual(ctx.external_group_key, 'g1')
        self.assertIn('vinculado', out)

    def test_ambiguous_universo_is_flagged_not_linked(self):
        out = self._run(
            universo=[
                {'external_group_key': 'g1', 'team_name': 'Benagalbón A'},
                {'external_group_key': 'g2', 'team_name': 'Benagalbón B'},
            ],
            commit=True,
        )
        ctx = WorkspaceCompetitionContext.objects.get(workspace=self.workspace, team=self.team)
        self.assertFalse(ctx.external_group_key)  # no se ató nada
        self.assertIn('ambiguo', out)

    def test_commit_links_preferente_when_no_universo(self):
        out = self._run(
            universo=[],
            preferente_url='https://www.lapreferente.com/E147/cd-benagalbon',
            commit=True,
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.preferente_url, 'https://www.lapreferente.com/E147/cd-benagalbon')
        ctx = WorkspaceCompetitionContext.objects.get(workspace=self.workspace, team=self.team)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_PREFERENTE)
        self.assertIn('La Preferente', out)

    def test_already_linked_is_left_alone(self):
        WorkspaceCompetitionContext.objects.create(
            workspace=self.workspace,
            team=self.team,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='already',
        )
        out = self._run(universo=[{'external_group_key': 'other', 'team_name': 'x'}], commit=True)
        ctx = WorkspaceCompetitionContext.objects.get(workspace=self.workspace, team=self.team)
        self.assertEqual(ctx.external_group_key, 'already')  # no lo re-vincula
        self.assertIn('ya enganchado', out)

    def test_unmatched_reported(self):
        out = self._run(universo=[], preferente_url='', commit=True)
        self.assertIn('sin liga', out)
