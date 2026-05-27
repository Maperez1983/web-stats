from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import Team, Workspace, WorkspaceMembership, WorkspaceTeam


class WorkspaceActiveSelectionTests(TestCase):
    def test_workspace_and_team_selection_persist_in_session(self):
        user = get_user_model().objects.create_user(username='workspace-switcher', password='pass-1234')
        team = Team.objects.create(name='Equipo switch', slug='equipo-switch', short_name='SW', is_primary=True)
        workspace = Workspace.objects.create(
            name='Club switch',
            slug='club-switch',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=team,
            owner_user=user,
            enabled_modules={},
            subscription_status='trial',
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=workspace, team=team, is_default=True)

        self.client.force_login(user)
        response = self.client.post(reverse('workspace-active'), {'workspace_id': workspace.id}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session.get('active_workspace_id') or 0), workspace.id)

        response = self.client.post(reverse('workspace-active-team'), {'team_id': team.id}, secure=True)
        self.assertEqual(response.status_code, 302)
        active_teams = self.client.session.get('active_team_by_workspace') or {}
        self.assertEqual(int(active_teams.get(str(workspace.id)) or 0), team.id)

    @patch('football.workspace_views.sync_workspace_competition_context')
    def test_workspace_sync_route_uses_active_workspace_context(self, mock_sync):
        user = get_user_model().objects.create_user(username='workspace-syncer', password='pass-1234')
        team = Team.objects.create(name='Equipo sync', slug='equipo-sync', short_name='SYN', is_primary=True)
        workspace = Workspace.objects.create(
            name='Club sync',
            slug='club-sync',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=team,
            owner_user=user,
            enabled_modules={},
            subscription_status='trial',
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=workspace, team=team, is_default=True)
        mock_sync.return_value = (SimpleNamespace(sync_status='ready', last_sync_at=timezone.now()), None)

        self.client.force_login(user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.post(reverse('workspace-sync-competition'), secure=True)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('status'), 'success')
        self.assertEqual(payload.get('sync_status'), 'ready')
        mock_sync.assert_called_once()
        self.assertEqual(mock_sync.call_args.kwargs.get('primary_team'), team)
