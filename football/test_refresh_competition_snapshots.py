from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from football.models import Team, Workspace, WorkspaceCompetitionContext


class RefreshCompetitionSnapshotsCommandTests(TestCase):
    def _make_context(self, slug, *, last_sync_at=None):
        team = Team.objects.create(
            name=f'Team {slug}',
            slug=f'team-{slug}',
            is_primary=True,
            preferente_url=f'https://www.lapreferente.com/E{slug}/team-{slug}',
        )
        workspace = Workspace.objects.create(
            name=f'Club {slug}', slug=f'club-{slug}', kind=Workspace.KIND_CLUB, primary_team=team
        )
        return WorkspaceCompetitionContext.objects.create(
            workspace=workspace,
            team=team,
            provider=WorkspaceCompetitionContext.PROVIDER_PREFERENTE,
            last_sync_at=last_sync_at,
        )

    def _run(self, **kwargs):
        out = StringIO()
        with mock.patch(
            'football.management.commands.refresh_competition_snapshots.sync_workspace_competition_context'
        ) as sync_mock:
            fake = mock.Mock(sync_status=WorkspaceCompetitionContext.STATUS_READY, sync_error='')
            sync_mock.return_value = (fake, '')
            call_command('refresh_competition_snapshots', stdout=out, **kwargs)
        return sync_mock, out.getvalue()

    def test_refreshes_all_stale_club_contexts(self):
        self._make_context('1', last_sync_at=None)
        self._make_context('2', last_sync_at=timezone.now() - timedelta(hours=48))

        sync_mock, output = self._run()

        self.assertEqual(sync_mock.call_count, 2)
        self.assertIn('Refrescados: 2', output)

    def test_throttle_skips_recently_synced(self):
        self._make_context('1', last_sync_at=timezone.now() - timedelta(hours=1))  # fresco
        self._make_context('2', last_sync_at=timezone.now() - timedelta(hours=48))  # viejo

        sync_mock, output = self._run(min_age_hours=6)

        self.assertEqual(sync_mock.call_count, 1)
        self.assertIn('omitidos: 1', output)

    def test_force_ignores_throttle(self):
        self._make_context('1', last_sync_at=timezone.now() - timedelta(minutes=5))

        sync_mock, _ = self._run(force=True)

        self.assertEqual(sync_mock.call_count, 1)

    def test_dry_run_does_not_sync(self):
        self._make_context('1', last_sync_at=None)

        sync_mock, output = self._run(dry_run=True)

        sync_mock.assert_not_called()
        self.assertIn('[dry]', output)
