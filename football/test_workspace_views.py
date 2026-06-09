from types import SimpleNamespace
from unittest.mock import patch
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import AppUserRole, StaffMember, Team, UserInvitation, Workspace, WorkspaceMembership, WorkspaceTeam


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


class PlatformWorkspaceTeamDetailTests(TestCase):
    def test_team_detail_hides_google_urls_from_stadium_fields(self):
        user = get_user_model().objects.create_user(username='team-detail-admin', password='pass-1234')
        primary_team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-detail',
            short_name='BEN',
            is_primary=True,
            home_stadium='https://www.google.com/search?client=safari&q=Campo+Municipal+de+Futbol+Cañada',
            home_stadium_address='https://www.google.com/url?sa=t&url=/maps/place//data%3Dbad',
        )
        cadete = Team.objects.create(
            name='Benagalbon c. d.',
            slug='benagalbon-cadete-detail',
            short_name='CAD',
            category='CADETE',
            game_format=Team.GAME_FORMAT_F11,
        )
        workspace = Workspace.objects.create(
            name='Benagalbón',
            slug='benagalbon-detail',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=primary_team,
            owner_user=user,
            enabled_modules={},
            subscription_status='trial',
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=workspace, team=primary_team, is_default=True)
        WorkspaceTeam.objects.create(workspace=workspace, team=cadete)

        self.client.force_login(user)
        response = self.client.get(reverse('platform-workspace-team-detail', args=[workspace.id, cadete.id]), secure=True)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('Campo Municipal de Futbol Cañada', body)
        self.assertIn('Sin dirección', body)
        self.assertNotIn('client=safari', body)
        self.assertNotIn('google.com/search', body)
        self.assertNotIn('google.com/url', body)


class StaffAccessInvitationTests(TestCase):
    def test_staff_create_can_generate_access_invitation(self):
        owner = get_user_model().objects.create_user(username='staff-owner', password='pass-1234')
        team = Team.objects.create(name='Staff Team', slug='staff-team', short_name='STF', is_primary=True)
        workspace = Workspace.objects.create(
            name='Staff Club',
            slug='staff-club',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=team,
            owner_user=owner,
            enabled_modules={},
            subscription_status='trial',
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=owner, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=workspace, team=team, is_default=True)

        self.client.force_login(owner)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session['active_team_by_workspace'] = {str(workspace.id): team.id}
        session.save()

        response = self.client.post(
            reverse('staff-member-create'),
            {
                'name': 'Ana Analista',
                'role_title': 'Analista',
                'email': 'ana.analista@example.com',
                'scope': 'team',
                'access_action': 'invite',
                'access_app_role': AppUserRole.ROLE_ANALYST,
                'access_member_role': WorkspaceMembership.ROLE_MEMBER,
                'access_valid_days': '14',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username='ana.analista')
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'ana.analista@example.com')
        self.assertEqual(user.app_role.role, AppUserRole.ROLE_ANALYST)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=user,
                role=WorkspaceMembership.ROLE_MEMBER,
            ).exists()
        )
        member = StaffMember.objects.get(workspace=workspace, name='Ana Analista')
        self.assertEqual(member.user, user)
        self.assertEqual(member.team, team)
        invitation = UserInvitation.objects.get(user=user, is_active=True, accepted_at__isnull=True)
        self.assertContains(response, reverse('user-invite-accept', args=[invitation.token]))


class DashboardPlatformAutoselectWorkspaceTests(TestCase):
    def test_platform_admin_without_context_gets_single_club_team_payload(self):
        team = Team.objects.create(name='Equipo dashboard', slug='equipo-dashboard', short_name='Dash', is_primary=True)
        user = get_user_model().objects.create_user(username='dash-admin', password='pass-1234', is_staff=True)
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_ADMIN)
        workspace = Workspace.objects.create(
            name='Club único',
            slug='club-unico',
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
        response = self.client.get(reverse('dashboard-data'), secure=True)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(int(payload.get('team', {}).get('id') or 0), team.id)

    def test_home_club_param_autoselects_owner_workspace_when_multiple(self):
        team1 = Team.objects.create(name='T1', slug='dash-t1', short_name='T1', is_primary=True)
        team2 = Team.objects.create(name='T2', slug='dash-t2', short_name='T2', is_primary=True)
        user = get_user_model().objects.create_user(username='dash-owner', password='pass-1234', is_staff=True)
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_ADMIN)
        ws_owned = Workspace.objects.create(
            name='Club owned',
            slug='club-owned',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=team1,
            owner_user=user,
            enabled_modules={},
            subscription_status='trial',
        )
        ws_other = Workspace.objects.create(
            name='Club other',
            slug='club-other',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=team2,
            owner_user=user,
            enabled_modules={},
            subscription_status='trial',
        )
        WorkspaceMembership.objects.create(workspace=ws_owned, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceMembership.objects.create(workspace=ws_other, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=ws_owned, team=team1, is_default=True)
        WorkspaceTeam.objects.create(workspace=ws_other, team=team2, is_default=True)

        self.client.force_login(user)
        response = self.client.get(f"{reverse('dashboard-data')}?home=club", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(int(payload.get('team', {}).get('id') or 0), team1.id)
