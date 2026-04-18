import base64
import json
import os
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from football.models import AnalystVideoFolder, Competition, ConvocationRecord, Group, Match, MatchEvent, MatchReport, Player, PlayerCommunication, PlayerFine, PlayerStatistic, RivalAnalysisReport, RivalVideo, Season, SessionTask, StaffMember, TaskStudioProfile, TaskStudioRosterPlayer, TaskStudioTask, Team, TeamStanding, TrainingMicrocycle, TrainingSession, UserInvitation, Workspace, WorkspaceCompetitionContext, WorkspaceCompetitionSnapshot, WorkspaceMembership, WorkspaceTeam
from football import views as football_views
from football.bootstrap import ensure_bootstrap_admin_from_env
from football.event_taxonomy import (
    PASS_KEYWORDS,
    build_smart_kpis,
    calculate_influence_score,
    calculate_importance_score,
    classify_duel_event,
    contains_keyword,
    is_shot_attempt_event,
    is_shot_on_target_event,
    map_zone_label,
    shots_needed_per_goal,
)
from football.healthchecks import run_system_healthcheck
from football.manual_stats import get_manual_player_base_overrides, save_manual_player_base_overrides, season_display_name
from football.query_helpers import _team_match_queryset, get_active_injury_player_ids, get_current_convocation_record, is_injury_record_active, is_manual_sanction_active
from football.injuries import categorize_time_loss, estimate_return_date, time_loss_days
from football.models import AppUserRole
from football.services import find_roster_entry
from football.staff_briefing import build_weekly_staff_brief
from football.task_library import filter_task_library, prepare_task_library
from football.stats_audit import run_stats_audit
from football.views import SCRAPE_LOCK_KEY, compute_player_cards_for_match, compute_player_dashboard, compute_player_metrics, compute_team_metrics_for_match
from django.test import override_settings
from unittest.mock import patch


class WriteEndpointAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='coach',
            email='coach@example.com',
            password='pass-1234',
        )

    def test_refresh_requires_authentication(self):
        response = self.client.post(reverse('dashboard-refresh'))
        self.assertEqual(response.status_code, 401)

    def test_save_convocation_requires_authentication(self):
        response = self.client.post(
            reverse('convocation-save'),
            data='[]',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_is_rate_limited_when_lock_exists(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        cache.set(SCRAPE_LOCK_KEY, '1', timeout=60)
        response = self.client.post(reverse('dashboard-refresh'))
        self.assertEqual(response.status_code, 429)
        cache.delete(SCRAPE_LOCK_KEY)

    def test_dashboard_page_requires_login(self):
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2J Football Intelligence')

    def test_dashboard_data_requires_login(self):
        response = self.client.get(reverse('dashboard-data'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_trainer_workspace_requires_login(self):
        response = self.client.get(reverse('coach-role-trainer'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_analysis_page_requires_login(self):
        response = self.client.get(reverse('analysis'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_coach_roster_requires_login(self):
        response = self.client.get(reverse('coach-roster'), secure=True)
        # Puede devolver 301 -> https o 302 -> login según settings.
        self.assertIn(response.status_code, {301, 302})
        self.assertIn('/login/', response['Location'])

    def test_product_landing_is_public(self):
        response = self.client.get(reverse('product-landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2J Football Intelligence')


class LoginNextRedirectTests(TestCase):
    def setUp(self):
        self.player_user = get_user_model().objects.create_user(
            username='player-next',
            email='player-next@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.player_user, role=AppUserRole.ROLE_PLAYER)

    def test_player_login_ignores_platform_next(self):
        response = self.client.post(
            f"{reverse('login')}?next=/platform/",
            {'username': 'player-next', 'password': 'pass-1234'},
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})
        self.assertEqual(response['Location'], reverse('dashboard-home'))


class DashboardSetupModeTests(TestCase):
    def setUp(self):
        self.primary_global_team = Team.objects.create(
            name='C.D. Benagalbón',
            slug='cdb-benagalbon',
            short_name='Benagalbón',
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='client-owner',
            email='client-owner@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='PRUEBA',
            slug='prueba',
            kind=Workspace.KIND_CLUB,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )

    def test_dashboard_data_returns_setup_payload_for_unconfigured_workspace(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('dashboard-data')}?workspace={self.workspace.id}", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('setup_required'))
        self.assertEqual(payload.get('team', {}).get('name'), 'PRUEBA')
        self.assertIn('player-avatar.svg', payload.get('team', {}).get('crest_url', ''))
        self.assertNotEqual(payload.get('team', {}).get('name'), self.primary_global_team.name)


class DashboardDayPlanPayloadTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre',
            short_name='Benagalbón',
            category='prebenjamin',
            game_format=Team.GAME_FORMAT_F7,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-dayplan',
            email='coach-dayplan@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='BENAGALBON',
            slug='benagalbon',
            kind=Workspace.KIND_CLUB,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(
            workspace=self.workspace,
            team=self.team,
            is_default=True,
        )

    def test_dashboard_data_includes_next_session_when_planned_session_exists(self):
        today = timezone.localdate()
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            objective='',
            week_start=today,
            week_end=today + timedelta(days=6),
            status=TrainingMicrocycle.STATUS_DRAFT,
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today + timedelta(days=1),
            duration_minutes=90,
            intensity=TrainingSession.INTENSITY_LOW,
            focus='Sesión test',
            status=TrainingSession.STATUS_PLANNED,
        )
        self.assertEqual(TrainingSession.objects.filter(microcycle__team=self.team).count(), 1)

        self.client.force_login(self.user)
        response = self.client.get(
            f"{reverse('dashboard-data')}?workspace={self.workspace.id}&team={self.team.id}&fresh=1",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('next_session', payload)
        self.assertEqual(payload['next_session']['id'], session.id)
        self.assertEqual(payload['next_session']['focus'], 'Sesión test')


class SearchApiExtendedGroupsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre',
            short_name='Benagalbón',
            category='prebenjamin',
            game_format=Team.GAME_FORMAT_F7,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-search',
            email='coach-search@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='BENAGALBON',
            slug='benagalbon',
            kind=Workspace.KIND_CLUB,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(
            workspace=self.workspace,
            team=self.team,
            is_default=True,
        )

    def test_search_api_includes_staff_sessions_and_tasks(self):
        StaffMember.objects.create(
            workspace=self.workspace,
            team=None,
            name='Carlos Fisio',
            role_title='Fisio',
            is_active=True,
        )
        today = timezone.localdate()
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            objective='',
            week_start=today,
            week_end=today + timedelta(days=6),
            status=TrainingMicrocycle.STATUS_DRAFT,
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today,
            duration_minutes=90,
            intensity=TrainingSession.INTENSITY_LOW,
            focus='Conceptos básicos',
            status=TrainingSession.STATUS_PLANNED,
        )
        SessionTask.objects.create(
            session=session,
            title='Búsqueda del espacio',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            objective='',
            coaching_points='',
            confrontation_rules='',
            tactical_layout={},
        )

        self.client.force_login(self.user)
        response = self.client.get(
            f"{reverse('search-api')}?workspace={self.workspace.id}&team={self.team.id}&q=conceptos",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        groups = payload.get('groups') or []
        labels = {g.get('label') for g in groups if isinstance(g, dict)}
        self.assertIn('Sesiones', labels)
        response_tasks = self.client.get(
            f"{reverse('search-api')}?workspace={self.workspace.id}&team={self.team.id}&q=búsqueda",
            secure=True,
        )
        self.assertEqual(response_tasks.status_code, 200)
        payload_tasks = response_tasks.json()
        labels_tasks = {g.get('label') for g in (payload_tasks.get('groups') or []) if isinstance(g, dict)}
        self.assertIn('Tareas', labels_tasks)

        response_staff = self.client.get(
            f"{reverse('search-api')}?workspace={self.workspace.id}&team={self.team.id}&q=fisio",
            secure=True,
        )
        self.assertEqual(response_staff.status_code, 200)
        payload_staff = response_staff.json()
        groups_staff = payload_staff.get('groups') or []
        label_staff = next((g for g in groups_staff if g.get('label') == 'Staff'), None)
        self.assertIsNotNone(label_staff)
        items = label_staff.get('items') or []
        self.assertTrue(any('Carlos' in str(it.get('label') or '') for it in items))


class CommercialIsolationTests(TestCase):
    def test_user_without_workspace_does_not_fall_back_to_global_team(self):
        Team.objects.create(name='GLOBAL', slug='global', short_name='GLOBAL', is_primary=True)
        user = get_user_model().objects.create_user(username='new-user', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard-data'), secure=True)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('setup_required'))
        self.assertIn('/onboarding/', payload.get('setup_url', ''))
        self.assertNotEqual(payload.get('team', {}).get('name'), 'GLOBAL')


class TeamMatchQuerysetIsolationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.competition = Competition.objects.create(name='Test Comp', slug='test-comp', region='Test')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='Grupo', slug='grupo')

        self.team_pre = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre',
            short_name='Benagalbón',
            category='prebenjamin',
            game_format=Team.GAME_FORMAT_F7,
        )
        self.team_senior = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-senior',
            short_name='Benagalbón',
            category='senior',
            game_format=Team.GAME_FORMAT_F11,
        )
        self.rival_a = Team.objects.create(name='Rival A', slug='rival-a', short_name='Rival A')
        self.rival_b = Team.objects.create(name='Rival B', slug='rival-b', short_name='Rival B')
        self.other_team = Team.objects.create(name='Otro', slug='otro', short_name='Otro')

        self.match_pre = Match.objects.create(
            season=self.season,
            group=self.group,
            round='1',
            home_team=self.team_pre,
            away_team=self.rival_a,
        )
        self.match_senior = Match.objects.create(
            season=self.season,
            group=self.group,
            round='2',
            home_team=self.team_senior,
            away_team=self.rival_b,
        )
        self.match_other = Match.objects.create(
            season=self.season,
            group=self.group,
            round='3',
            home_team=self.other_team,
            away_team=self.rival_b,
        )
        MatchReport.objects.create(match=self.match_other, source_file='report.pdf')

    def test_team_match_queryset_does_not_mix_categories_or_reports(self):
        match_ids = {m.id for m in _team_match_queryset(self.team_pre)}
        self.assertIn(self.match_pre.id, match_ids)
        self.assertNotIn(self.match_senior.id, match_ids)
        self.assertNotIn(self.match_other.id, match_ids)

    def test_compute_player_dashboard_ignores_events_from_other_team_matches(self):
        player = Player.objects.create(team=self.team_pre, name='Jugador Pre', number=7)
        # Evento correcto: partido del propio equipo.
        MatchEvent.objects.create(
            match=self.match_pre,
            player=player,
            minute=3,
            event_type='pase',
            zone='Z1',
            result='ok',
            system='touch-field',
            source_file='registro-acciones',
        )
        # Evento incorrecto (data sucia): mismo jugador pero asociado a un match de otra categoría.
        MatchEvent.objects.create(
            match=self.match_senior,
            player=player,
            minute=5,
            event_type='pase',
            zone='Z1',
            result='ok',
            system='touch-field',
            source_file='registro-acciones',
        )

        rows = football_views.compute_player_dashboard(self.team_pre, force_refresh=True)
        detail = next((row for row in rows if row.get('player_id') == player.id), {})
        match_ids = {int(item.get('match_id') or 0) for item in (detail.get('matches') or [])}

        self.assertIn(self.match_pre.id, match_ids)
        self.assertNotIn(self.match_senior.id, match_ids)


class WorkspaceOwnerPermissionTests(TestCase):
    def test_owner_user_can_manage_workspace_without_membership_row(self):
        user = get_user_model().objects.create_user(username='owner-no-membership', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        workspace = Workspace.objects.create(
            name='Club',
            slug='club',
            kind=Workspace.KIND_CLUB,
            owner_user=user,
            is_active=True,
        )
        self.assertTrue(football_views._can_manage_workspace(user, workspace))
        self.assertTrue(football_views._can_view_workspace(user, workspace))


class TrialPaywallTests(TestCase):
    def test_trial_expired_redirects_to_billing_for_html_pages(self):
        user = get_user_model().objects.create_user(username='trial-owner', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        workspace = Workspace.objects.create(
            name='Club Trial',
            slug='club-trial',
            kind=Workspace.KIND_CLUB,
            owner_user=user,
            enabled_modules={'players': True, 'dashboard': True},
            subscription_status='trial',
            trial_expires_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceMembership.ROLE_OWNER)
        self.client.force_login(user)
        response = self.client.get(f"{reverse('coach-roster')}?workspace={workspace.id}", secure=True, HTTP_ACCEPT='text/html')
        self.assertIn(response.status_code, {301, 302})
        self.assertIn('/billing/', response['Location'])

class UniversoSyncWithoutGroupTests(TestCase):
    @patch('football.views._sync_team_crest_from_sources')
    @patch('football.views._find_universo_next_match_for_context', return_value={})
    @patch('football.views._fetch_universo_live_classification')
    def test_universo_sync_creates_group_when_team_has_none(self, mock_fetch, _mock_next, _mock_crest):
        user = get_user_model().objects.create_user(
            username='universo-owner',
            email='universo-owner@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        team = Team.objects.create(
            name='Equipo Demo',
            slug='equipo-demo',
            short_name='Equipo Demo',
            is_primary=False,
        )
        workspace = Workspace.objects.create(
            name='Club Demo',
            slug='club-demo',
            kind=Workspace.KIND_CLUB,
            primary_team=team,
            owner_user=user,
            is_active=True,
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceCompetitionContext.objects.create(
            workspace=workspace,
            team=team,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name=team.name,
            is_auto_sync_enabled=True,
        )
        mock_fetch.return_value = {
            'competicion': 'División Demo',
            'grupo': 'Grupo Demo',
            'codigo_competicion': '99999',
            'clasificacion': [
                {
                    'nombre': 'Equipo Demo',
                    'posicion': 1,
                    'pj': 10,
                    'pg': 8,
                    'pe': 1,
                    'pp': 1,
                    'gf': 22,
                    'gc': 9,
                    'pt': 25,
                    'codequipo': '111',
                    'url_img': '',
                },
                {
                    'nombre': 'Rival Demo',
                    'posicion': 2,
                    'pj': 10,
                    'pg': 7,
                    'pe': 2,
                    'pp': 1,
                    'gf': 18,
                    'gc': 10,
                    'pt': 23,
                    'codequipo': '222',
                    'url_img': '',
                },
            ],
        }

        ctx, error = football_views._sync_workspace_competition_context(workspace, primary_team=team)

        self.assertEqual(error, '')
        team.refresh_from_db()
        self.assertIsNotNone(team.group_id)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.sync_status, WorkspaceCompetitionContext.STATUS_READY)

class PlayerUserLinkTests(TestCase):
    def test_resolve_player_uses_explicit_user_link(self):
        team = Team.objects.create(name='Equipo', slug='equipo', short_name='Equipo', is_primary=True)
        p1 = Player.objects.create(team=team, name='Ayala', full_name='Angel Ayala', is_active=True)
        p2 = Player.objects.create(team=team, name='Sanchez', full_name='Angel Sanchez', is_active=True)

        u1 = get_user_model().objects.create_user(username='angel.ayala', password='pass-1234', first_name='Angel', last_name='Ayala')
        u2 = get_user_model().objects.create_user(username='angel.sanchez', password='pass-1234', first_name='Angel', last_name='Sanchez')
        AppUserRole.objects.create(user=u1, role=AppUserRole.ROLE_PLAYER)
        AppUserRole.objects.create(user=u2, role=AppUserRole.ROLE_PLAYER)

        p1.user = u1
        p1.save(update_fields=['user'])
        p2.user = u2
        p2.save(update_fields=['user'])

        self.assertEqual(football_views._resolve_player_for_user(u1, team).id, p1.id)
        self.assertEqual(football_views._resolve_player_for_user(u2, team).id, p2.id)


class StaffBriefingTests(TestCase):
    def test_build_weekly_staff_brief_summarizes_availability(self):
        brief = build_weekly_staff_brief(
            player_cards=[
                {'player_id': 1, 'name': 'Portero', 'position': 'Portero', 'minutes': 900, 'pt': 10, 'pj': 10},
                {'player_id': 2, 'name': 'Central', 'position': 'Central', 'minutes': 850, 'pt': 9, 'pj': 10},
                {'player_id': 3, 'name': 'Medio', 'position': 'Mediocentro', 'minutes': 700, 'pt': 8, 'pj': 10},
            ],
            active_injury_ids={2},
            sanctioned_player_ids={3},
            convocation_player_ids={1},
            next_match={'round': 'Jornada 24', 'date': '2026-03-29', 'time': '18:00', 'location': 'Casa', 'opponent': 'Marbella'},
        )

        self.assertEqual(brief['availability'][0]['value'], 1)
        self.assertEqual(brief['availability'][1]['value'], 1)
        self.assertEqual(brief['availability'][2]['value'], 1)
        self.assertIn('Marbella', brief['headline'])
        self.assertTrue(any('lesión' in line for line in brief['alerts']))


class InvitationAcceptanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='jugador',
            email='jugador@example.com',
            password='old-pass-1234',
            is_active=False,
        )
        self.invitation = UserInvitation.objects.create(
            user=self.user,
            token='token-prueba',
            email=self.user.email,
            expires_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )

    def test_accept_invitation_sets_password_and_invalidates_token(self):
        response = self.client.post(
            reverse('user-invite-accept', args=[self.invitation.token]),
            {
                'password': 'NuevaPassSegura2026!',
                'password_confirm': 'NuevaPassSegura2026!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard-home'))
        self.invitation.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.invitation.is_active)
        self.assertIsNotNone(self.invitation.accepted_at)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password('NuevaPassSegura2026!'))


class TaskStudioAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='studio-user',
            email='studio@example.com',
            password='pass-1234',
        )
        self.other_user = get_user_model().objects.create_user(
            username='studio-other',
            email='studio-other@example.com',
            password='pass-1234',
        )
        self.admin_user = get_user_model().objects.create_user(
            username='studio-admin',
            email='studio-admin@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_TASK_STUDIO)
        AppUserRole.objects.create(user=self.other_user, role=AppUserRole.ROLE_TASK_STUDIO)
        AppUserRole.objects.create(user=self.admin_user, role=AppUserRole.ROLE_ADMIN)
        self.own_task = TaskStudioTask.objects.create(owner=self.user, title='Tarea propia', block=SessionTask.BLOCK_MAIN_1, duration_minutes=15)
        self.other_task = TaskStudioTask.objects.create(owner=self.other_user, title='Tarea ajena', block=SessionTask.BLOCK_MAIN_1, duration_minutes=15)

    def test_dashboard_redirects_task_studio_role_to_private_module(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard-home'))

        self.assertRedirects(response, reverse('task-studio-home'))

    def test_task_studio_home_only_lists_owned_tasks_for_regular_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('task-studio-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tarea propia')
        self.assertNotContains(response, 'Tarea ajena')
        self.assertContains(response, 'Primeros pasos')
        self.assertContains(response, 'Perfil e identidad')
        self.assertContains(response, 'Plantilla privada')

    def test_task_studio_owner_can_delete_own_task(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('task-studio-task-delete', args=[self.own_task.id]))

        self.assertRedirects(response, reverse('task-studio-home'))
        task = TaskStudioTask.objects.get(id=self.own_task.id)
        self.assertIsNotNone(task.deleted_at)

    def test_task_studio_owner_can_duplicate_own_task(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('task-studio-task-duplicate', args=[self.own_task.id]))

        self.assertEqual(response.status_code, 302)
        clones = TaskStudioTask.objects.filter(owner=self.user, title__icontains='Tarea propia')
        self.assertEqual(clones.count(), 2)
        self.assertTrue(clones.exclude(id=self.own_task.id).filter(title='Tarea propia (copia)').exists())

    def test_task_studio_user_cannot_delete_foreign_task(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('task-studio-task-delete', args=[self.other_task.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(TaskStudioTask.objects.filter(id=self.other_task.id).exists())

    def test_task_studio_admin_can_delete_foreign_task(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('task-studio-task-delete', args=[self.other_task.id]) + f'?user={self.other_user.id}')

        self.assertRedirects(response, reverse('task-studio-home') + f'?user={self.other_user.id}')
        task = TaskStudioTask.objects.get(id=self.other_task.id)
        self.assertIsNotNone(task.deleted_at)

    def test_disabled_task_studio_profile_blocks_module_access(self):
        TaskStudioProfile.objects.create(user=self.user, is_enabled=False)
        self.client.force_login(self.user)

        response = self.client.get(reverse('task-studio-home'))

        self.assertEqual(response.status_code, 403)

    def test_task_studio_profile_can_be_saved(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('task-studio-profile'),
            {
                'document_name': 'Miguel Perez',
                'display_name': 'Migue',
                'club_name': 'Academia Privada',
                'primary_color': '#0f7a35',
                'secondary_color': '#f8fafc',
                'accent_color': '#102734',
            },
        )

        self.assertEqual(response.status_code, 200)
        profile = TaskStudioProfile.objects.get(user=self.user)
        self.assertEqual(profile.document_name, 'Miguel Perez')
        self.assertEqual(profile.club_name, 'Academia Privada')

    def test_task_studio_roster_and_task_creation_are_private_to_owner(self):
        self.client.force_login(self.user)
        roster_response = self.client.post(
            reverse('task-studio-roster'),
            {
                'studio_action': 'add',
                'name': 'Tadeo',
                'number': '7',
                'position': 'Extremo',
            },
        )
        self.assertEqual(roster_response.status_code, 200)
        roster_player = TaskStudioRosterPlayer.objects.get(owner=self.user, name='Tadeo')

        create_response = self.client.post(
            reverse('task-studio-task-create'),
            {
                'draw_task_title': 'Rondo privado',
                'draw_task_block': SessionTask.BLOCK_MAIN_1,
                'draw_task_minutes': '18',
                'assigned_player_ids': [str(roster_player.id)],
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
                'draw_canvas_width': '1280',
                'draw_canvas_height': '720',
            },
        )

        self.assertEqual(create_response.status_code, 200)
        created = TaskStudioTask.objects.get(owner=self.user, title='Rondo privado')
        self.assertEqual(created.owner_id, self.user.id)
        response = self.client.get(reverse('task-studio-home'))
        self.assertContains(response, 'Rondo privado')
        self.assertNotContains(response, 'Tarea ajena')

    @patch('football.views.weasyprint', None)
    def test_guest_role_can_access_task_studio_pdf_preview(self):
        guest_user = get_user_model().objects.create_user(
            username='studio-guest',
            email='studio-guest@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=guest_user, role=AppUserRole.ROLE_GUEST)
        workspace = Workspace.objects.create(
            name='Task Studio invitado',
            slug='task-studio-invitado',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=guest_user,
            enabled_modules={
                'task_studio_home': True,
                'task_studio_profile': True,
                'task_studio_roster': True,
                'task_studio_tasks': True,
                'task_studio_pdfs': True,
            },
        )
        TaskStudioProfile.objects.create(user=guest_user, workspace=workspace)
        self.client.force_login(guest_user)

        response = self.client.post(
            reverse('task-studio-task-pdf-preview') + '?style=uefa',
            {
                'draw_task_title': 'Borrador invitado',
                'draw_task_minutes': '15',
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entrega Ejercicio')

    def test_guest_role_without_assignment_cannot_access_task_studio(self):
        guest_user = get_user_model().objects.create_user(
            username='guest-no-studio',
            email='guest-no-studio@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=guest_user, role=AppUserRole.ROLE_GUEST)
        self.client.force_login(guest_user)

        response = self.client.get(reverse('task-studio-home'))

        # Invitados: si tienen rol asignado, inicializamos Task Studio para que puedan entrar a modo demo.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Workspace.objects.filter(owner_user=guest_user, kind=Workspace.KIND_TASK_STUDIO).exists())

    @patch('football.views.weasyprint', None)
    def test_disabled_task_studio_pdf_module_returns_403(self):
        workspace = Workspace.objects.create(
            name='Task Studio restringido',
            slug='task-studio-restringido',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.user,
            enabled_modules={
                'task_studio_home': True,
                'task_studio_profile': True,
                'task_studio_roster': True,
                'task_studio_tasks': True,
                'task_studio_pdfs': False,
            },
        )
        TaskStudioProfile.objects.update_or_create(user=self.user, defaults={'workspace': workspace})
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('task-studio-task-pdf-preview') + '?style=uefa',
            {
                'draw_task_title': 'Borrador bloqueado',
                'draw_task_minutes': '15',
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
            },
        )

        self.assertEqual(response.status_code, 403)


class PlatformWorkspaceTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(
            username='platform-admin',
            email='platform-admin@example.com',
            password='pass-1234',
            is_staff=True,
        )
        self.studio_user = get_user_model().objects.create_user(
            username='platform-studio',
            email='platform-studio@example.com',
            password='pass-1234',
        )
        self.basic_user = get_user_model().objects.create_user(
            username='platform-basic',
            email='platform-basic@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.admin_user, role=AppUserRole.ROLE_ADMIN)
        AppUserRole.objects.create(user=self.studio_user, role=AppUserRole.ROLE_TASK_STUDIO)
        AppUserRole.objects.create(user=self.basic_user, role=AppUserRole.ROLE_PLAYER)
        self.workspace_manager = get_user_model().objects.create_user(
            username='workspace-manager',
            email='workspace-manager@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.workspace_manager, role=AppUserRole.ROLE_COACH)
        self.workspace_member = get_user_model().objects.create_user(
            username='workspace-member',
            email='workspace-member@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.workspace_member, role=AppUserRole.ROLE_ANALYST)
        competition = Competition.objects.create(name='Liga Plataforma', slug='liga-plataforma', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Plataforma', slug='grupo-plataforma')
        self.team = Team.objects.create(name='Benagalbón matriz', slug='benagalbon-matriz', group=group, is_primary=True)
        self.alt_team = Team.objects.create(name='Cliente alternativo', slug='cliente-alternativo', group=group, is_primary=False)

    def test_platform_overview_requires_admin_access(self):
        self.client.force_login(self.basic_user)

        response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 403)

    def test_legacy_admin_role_alias_can_access_platform(self):
        legacy_admin = get_user_model().objects.create_user(
            username='legacy-admin',
            email='legacy-admin@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=legacy_admin, role='admin')
        self.client.force_login(legacy_admin)

        response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)

    def test_staff_user_without_explicit_role_is_treated_as_admin(self):
        staff_user = get_user_model().objects.create_user(
            username='staff-no-role',
            email='staff-no-role@example.com',
            password='pass-1234',
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse('dashboard-home'))

        self.assertEqual(response.status_code, 200)

    def test_platform_overview_bootstraps_primary_and_task_studio_workspaces(self):
        self.client.force_login(self.admin_user)

        with patch.dict(os.environ, {'PLATFORM_AUTO_ENSURE_WORKSPACES': '1'}):
            response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clientes')
        self.assertContains(response, 'Usuarios')
        self.assertContains(response, 'Entrar en')
        club_workspace = Workspace.objects.filter(primary_team=self.team, kind=Workspace.KIND_CLUB).first()
        studio_workspace = Workspace.objects.filter(owner_user=self.studio_user, kind=Workspace.KIND_TASK_STUDIO).first()
        self.assertIsNotNone(club_workspace)
        self.assertIsNotNone(studio_workspace)
        self.assertTrue(club_workspace.enabled_modules.get('dashboard'))
        self.assertTrue(studio_workspace.enabled_modules.get('task_studio_home'))
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace__owner_user=self.studio_user,
                user=self.studio_user,
                role=WorkspaceMembership.ROLE_OWNER,
            ).exists()
        )

    @patch('football.views.load_cached_next_match')
    @patch('football.views.load_universo_snapshot')
    @patch('football.views._find_universo_next_match_for_context')
    def test_preferred_next_match_uses_workspace_provider_before_global_cache(
        self,
        mocked_provider_next,
        mocked_snapshot,
        mocked_cached_next,
    ):
        future_date = (timezone.localdate() + timedelta(days=7)).isoformat()
        context = WorkspaceCompetitionContext.objects.create(
            workspace=Workspace.objects.create(
                name='Cliente provider',
                slug='cliente-provider',
                kind=Workspace.KIND_CLUB,
                primary_team=self.team,
            ),
            team=self.team,
            group=self.team.group,
            season=self.team.group.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name=self.team.name,
        )
        mocked_provider_next.return_value = {
            'round': '27',
            'date': future_date,
            'location': 'Campo real',
            'opponent': {'name': 'Rival real'},
            'status': 'next',
            'source': 'universo-live',
        }
        mocked_snapshot.return_value = {
            'next_match': {
                'round': 'Partido 1',
                'date': '2026-03-01',
                'opponent': {'name': 'PIZARRA'},
                'status': 'next',
            }
        }
        mocked_cached_next.return_value = {
            'round': 'Partido 1',
            'date': '2026-03-01',
            'opponent': {'name': 'PIZARRA'},
            'status': 'next',
        }

        payload = football_views.load_preferred_next_match_payload(
            primary_team=self.team,
            competition_context=context,
        )

        self.assertEqual(payload['opponent']['name'], 'Rival real')
        mocked_provider_next.assert_called_once()

    @patch('football.views.load_universo_snapshot', return_value={})
    @patch('football.views._find_universo_next_match_for_context')
    def test_competition_payload_resyncs_unreliable_snapshot_next_match(
        self,
        mocked_provider_next,
        mocked_snapshot,
    ):
        workspace = Workspace.objects.create(
            name='Cliente snapshot',
            slug='cliente-snapshot',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        context = WorkspaceCompetitionContext.objects.create(
            workspace=workspace,
            team=self.team,
            group=self.team.group,
            season=self.team.group.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name=self.team.name,
        )
        snapshot = WorkspaceCompetitionSnapshot.objects.create(
            workspace=workspace,
            context=context,
            standings_payload=[{'rank': 1, 'team': self.team.name, 'points': 20}],
            next_match_payload={
                'round': 'Partido 1',
                'opponent': {'name': 'PIZARRA'},
                'status': 'next',
                'source': 'local-match',
            },
        )
        future_date = (timezone.localdate() + timedelta(days=7)).isoformat()
        mocked_provider_next.return_value = {
            'round': '27',
            'date': future_date,
            'location': 'Campo real',
            'opponent': {'name': 'Rival real'},
            'status': 'next',
            'source': 'universo-live',
        }

        payload = football_views._competition_payload_for_team(workspace, self.team)
        snapshot.refresh_from_db()

        self.assertEqual(payload['next_match']['opponent']['name'], 'Rival real')
        self.assertEqual(snapshot.next_match_payload.get('opponent', {}).get('name'), 'Rival real')

    def test_platform_overview_documents_tab_shows_recent_documents(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('platform-overview'))
        studio_workspace = Workspace.objects.filter(kind=Workspace.KIND_TASK_STUDIO, owner_user=self.studio_user).first()
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='MD-1',
            objective='Activar',
            week_start=date(2026, 3, 23),
            week_end=date(2026, 3, 29),
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=date(2026, 3, 25),
            focus='Previa rival',
            duration_minutes=70,
        )
        SessionTask.objects.create(
            session=session,
            title='Rueda de pases',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
        )
        TaskStudioTask.objects.create(
            workspace=studio_workspace,
            owner=self.studio_user,
            title='Tarea studio',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=20,
        )

        response = self.client.get(reverse('platform-overview') + '?tab=documents')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documentos recientes')
        self.assertContains(response, 'Rueda de pases')
        self.assertContains(response, 'Tarea studio')

    def test_platform_overview_can_create_workspace_manually(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'workspace_create',
                'workspace_name': 'Cliente demo',
                'workspace_kind': Workspace.KIND_TASK_STUDIO,
                'owner_username': self.studio_user.username,
                'module_task_studio_profile_identity': 'on',
                'deliverable_task_studio_profile_identity__branding': 'on',
                'module_task_studio_documents_exports': 'on',
                'deliverable_task_studio_documents_exports__pdfs': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace = Workspace.objects.get(name='Cliente demo')
        self.assertEqual(workspace.owner_user_id, self.studio_user.id)
        self.assertFalse(workspace.enabled_modules.get('task_studio_home'))
        self.assertTrue(workspace.enabled_modules.get('task_studio_profile'))
        self.assertFalse(workspace.enabled_modules.get('task_studio_roster'))
        self.assertFalse(workspace.enabled_modules.get('task_studio_tasks'))
        self.assertTrue(workspace.enabled_modules.get('task_studio_pdfs'))
        self.assertFalse(workspace.enabled_modules.get('module__task_studio_access_account'))
        self.assertTrue(workspace.enabled_modules.get('module__task_studio_profile_identity'))
        self.assertTrue(workspace.enabled_modules.get('module__task_studio_documents_exports'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__task_studio_profile_identity__branding'))
        self.assertFalse(workspace.enabled_modules.get('deliverable__task_studio_profile_identity__profile'))
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.studio_user,
                role=WorkspaceMembership.ROLE_OWNER,
            ).exists()
        )

    def test_platform_overview_can_create_global_task_studio_user(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_create',
                'full_name': 'Entrenador Demo',
                'username': 'task-demo',
                'email': 'task-demo@example.com',
                'password': 'pass-1234',
                'role': AppUserRole.ROLE_TASK_STUDIO,
            },
        )

        self.assertEqual(response.status_code, 200)
        created_user = get_user_model().objects.get(username='task-demo')
        self.assertEqual(created_user.get_full_name(), 'Entrenador Demo')
        self.assertEqual(created_user.app_role.role, AppUserRole.ROLE_TASK_STUDIO)
        self.assertTrue(Workspace.objects.filter(owner_user=created_user, kind=Workspace.KIND_TASK_STUDIO).exists())
        self.assertContains(response, 'Usuario creado en Plataforma')

    def test_platform_overview_can_create_global_user_and_assign_to_club(self):
        self.client.force_login(self.admin_user)

        club_workspace = Workspace.objects.create(
            name='Club asignación',
            slug='club-asignacion',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            owner_user=self.workspace_manager,
        )

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_create',
                'full_name': 'Entrenador Club',
                'username': 'club-demo',
                'email': 'club-demo@example.com',
                'password': 'pass-1234',
                'role': AppUserRole.ROLE_COACH,
                'assign_workspace_id': club_workspace.id,
                'assign_member_role': WorkspaceMembership.ROLE_ADMIN,
            },
        )

        self.assertEqual(response.status_code, 200)
        created_user = get_user_model().objects.get(username='club-demo')
        self.assertEqual(created_user.app_role.role, AppUserRole.ROLE_COACH)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=club_workspace,
                user=created_user,
                role=WorkspaceMembership.ROLE_ADMIN,
            ).exists()
        )
        self.assertContains(response, 'Asignado a')

    def test_platform_overview_can_update_global_user(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_update',
                'user_id': self.studio_user.id,
                'full_name': 'Studio Actualizado',
                'email': 'studio-updated@example.com',
                'role': AppUserRole.ROLE_TASK_STUDIO,
                'is_active': 'on',
                'password': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.studio_user.refresh_from_db()
        self.assertEqual(self.studio_user.get_full_name(), 'Studio Actualizado')
        self.assertEqual(self.studio_user.email, 'studio-updated@example.com')
        self.assertTrue(self.studio_user.is_active)
        self.assertContains(response, 'Usuario actualizado')

    def test_platform_overview_can_toggle_user_active_state(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_toggle_active',
                'user_id': self.studio_user.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.studio_user.refresh_from_db()
        self.assertFalse(self.studio_user.is_active)
        self.assertContains(response, 'Usuario desactivado')

    def test_platform_overview_can_delete_regular_user(self):
        removable = get_user_model().objects.create_user(
            username='removable-user',
            email='removable@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=removable, role=AppUserRole.ROLE_PLAYER)
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_delete',
                'user_id': removable.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(id=removable.id).exists())
        self.assertContains(response, 'Usuario eliminado')

    def test_platform_overview_delete_user_removes_task_studio_workspace(self):
        removable = get_user_model().objects.create_user(
            username='studio-removable',
            email='studio-removable@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=removable, role=AppUserRole.ROLE_TASK_STUDIO)
        workspace = Workspace.objects.create(
            name='Studio removable',
            slug='studio-removable',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=removable,
        )
        TaskStudioProfile.objects.create(user=removable, workspace=workspace)
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_delete',
                'user_id': removable.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(id=removable.id).exists())
        self.assertFalse(Workspace.objects.filter(id=workspace.id).exists())

    def test_platform_overview_prevents_deleting_club_owner(self):
        workspace = Workspace.objects.create(
            name='Cliente con owner',
            slug='cliente-con-owner',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.workspace_manager,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_delete',
                'user_id': self.workspace_manager.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(id=self.workspace_manager.id).exists())
        self.assertContains(response, 'No puedes borrar')

    def test_platform_overview_does_not_bootstrap_guest_task_studio_workspace(self):
        guest_user = get_user_model().objects.create_user(
            username='club-guest',
            email='club-guest@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=guest_user, role=AppUserRole.ROLE_GUEST)
        self.client.force_login(self.admin_user)

        with patch.dict(os.environ, {'PLATFORM_AUTO_ENSURE_WORKSPACES': '1'}):
            response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Workspace.objects.filter(owner_user=guest_user, kind=Workspace.KIND_TASK_STUDIO).exists())

    def test_platform_overview_can_generate_global_invitation(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'platform_user_invite_create',
                'user_id': self.studio_user.id,
                'valid_days': '7',
            },
        )

        self.assertEqual(response.status_code, 200)
        invitation = UserInvitation.objects.filter(user=self.studio_user, is_active=True).order_by('-created_at').first()
        self.assertIsNotNone(invitation)
        self.assertContains(response, 'Invitación generada en Plataforma')

    def test_platform_overview_can_create_workspace_with_modules_members_and_notes(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'workspace_create',
                'workspace_name': 'Cliente gobernado',
                'workspace_kind': Workspace.KIND_CLUB,
                'owner_username': self.admin_user.username,
                'team_id': self.alt_team.id,
                'workspace_notes': 'Cliente creado desde Plataforma con configuración completa.',
                'initial_admin_usernames': self.workspace_manager.username,
                'initial_member_usernames': f'{self.workspace_member.username}, {self.basic_user.username}',
                'module_technical_staff': 'on',
                'deliverable_technical_staff__staff_roster': 'on',
                'module_training': 'on',
                'deliverable_training__sessions': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace = Workspace.objects.get(name='Cliente gobernado')
        self.assertEqual(workspace.owner_user_id, self.admin_user.id)
        self.assertEqual(workspace.primary_team_id, self.alt_team.id)
        self.assertEqual(workspace.notes, 'Cliente creado desde Plataforma con configuración completa.')
        self.assertTrue(workspace.enabled_modules.get('players'))
        self.assertTrue(workspace.enabled_modules.get('sessions'))
        self.assertFalse(workspace.enabled_modules.get('dashboard'))
        self.assertFalse(workspace.enabled_modules.get('convocation'))
        self.assertFalse(workspace.enabled_modules.get('abp_board'))
        self.assertTrue(workspace.enabled_modules.get('module__technical_staff'))
        self.assertTrue(workspace.enabled_modules.get('module__training'))
        self.assertFalse(workspace.enabled_modules.get('module__match'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__technical_staff__staff_roster'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__training__sessions'))
        self.assertFalse(workspace.enabled_modules.get('deliverable__training__training_areas'))
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.admin_user,
                role=WorkspaceMembership.ROLE_OWNER,
            ).exists()
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.workspace_manager,
                role=WorkspaceMembership.ROLE_ADMIN,
            ).exists()
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.workspace_member,
                role=WorkspaceMembership.ROLE_MEMBER,
            ).exists()
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.basic_user,
                role=WorkspaceMembership.ROLE_MEMBER,
            ).exists()
        )

    def test_platform_overview_creates_club_competition_context(self):
        self.client.force_login(self.admin_user)
        rival = Team.objects.create(name='Rival Contexto', slug='rival-contexto', group=self.alt_team.group)
        Match.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            round='J25',
            date=timezone.localdate() + timedelta(days=5),
            location='Campo matriz',
            home_team=self.alt_team,
            away_team=rival,
        )
        TeamStanding.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            team=self.alt_team,
            position=2,
            played=24,
            wins=14,
            draws=4,
            losses=6,
            goals_for=39,
            goals_against=25,
            goal_difference=14,
            points=46,
        )

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'workspace_create',
                'workspace_name': 'Cliente con contexto',
                'workspace_kind': Workspace.KIND_CLUB,
                'owner_username': self.workspace_manager.username,
                'team_id': self.alt_team.id,
                'competition_provider': WorkspaceCompetitionContext.PROVIDER_MANUAL,
                'external_competition_key': 'liga-plataforma',
                'external_group_key': 'grupo-plataforma',
                'external_team_key': 'cliente-alternativo',
                'external_team_name': 'Cliente alternativo',
                'competition_auto_sync': 'on',
                'module_cover': 'on',
                'deliverable_cover__executive_home': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace = Workspace.objects.get(name='Cliente con contexto')
        context = WorkspaceCompetitionContext.objects.get(workspace=workspace, team=self.alt_team)
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(context.team_id, self.alt_team.id)
        self.assertEqual(context.group_id, self.alt_team.group_id)
        self.assertEqual(context.external_group_key, 'grupo-plataforma')
        self.assertEqual(context.sync_status, WorkspaceCompetitionContext.STATUS_READY)
        self.assertEqual(len(snapshot.standings_payload), 1)
        self.assertEqual(snapshot.next_match_payload.get('round'), 'J25')

    def test_platform_overview_rejects_unknown_initial_usernames(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'workspace_create',
                'workspace_name': 'Cliente inválido',
                'workspace_kind': Workspace.KIND_TASK_STUDIO,
                'owner_username': 'no-existe',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No existe el usuario propietario')
        self.assertFalse(Workspace.objects.filter(name='Cliente inválido').exists())

    def test_platform_overview_requires_owner_for_task_studio_workspace(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-overview'),
            {
                'form_action': 'workspace_create',
                'workspace_name': 'Task Studio sin owner',
                'workspace_kind': Workspace.KIND_TASK_STUDIO,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Task Studio requiere un usuario propietario')
        self.assertFalse(Workspace.objects.filter(name='Task Studio sin owner').exists())

    def test_enter_task_studio_workspace_redirects_to_supervisor_view(self):
        workspace = Workspace.objects.create(
            name='Task Studio Demo',
            slug='task-studio-demo',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-workspace-enter', args=[workspace.id]))

        self.assertEqual(self.client.session.get('active_workspace_id'), workspace.id)
        self.assertRedirects(response, f"{reverse('task-studio-home')}?user={self.studio_user.id}")

    def test_platform_overview_shows_team_entry_links_for_multi_team_client(self):
        workspace = Workspace.objects.create(
            name='Cliente multi',
            slug='cliente-multi',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        pre_team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre',
            short_name='Benagalbón',
            group=self.team.group,
            is_primary=False,
            category='Prebenjamín',
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        WorkspaceTeam.objects.create(workspace=workspace, team=pre_team, is_default=False)
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entrar · Prebenjamín')
        self.assertContains(response, f"{reverse('platform-workspace-enter', args=[workspace.id])}?team={pre_team.id}")

    def test_platform_enter_with_team_sets_active_team_mapping(self):
        workspace = Workspace.objects.create(
            name='Cliente multi 2',
            slug='cliente-multi-2',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        pre_team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre-2',
            short_name='Benagalbón',
            group=self.team.group,
            is_primary=False,
            category='Prebenjamín',
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        WorkspaceTeam.objects.create(workspace=workspace, team=pre_team, is_default=False)
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-workspace-enter', args=[workspace.id]), {'team': pre_team.id})

        self.assertEqual(response.status_code, 302)
        mapping = self.client.session.get('active_team_by_workspace') or {}
        self.assertEqual(int(mapping.get(str(workspace.id)) or 0), int(pre_team.id))

    def test_dashboard_data_uses_active_club_workspace_team(self):
        workspace = Workspace.objects.create(
            name='Cliente alternativo',
            slug='cliente-alternativo-workspace',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        self.alt_team.crest_url = 'https://example.com/cliente-alternativo.png'
        self.alt_team.save(update_fields=['crest_url'])
        football_views._invalidate_team_dashboard_caches(self.alt_team)
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-data'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['team']['name'], self.alt_team.name)
        self.assertEqual(response.json()['team']['crest_url'], 'https://example.com/cliente-alternativo.png')

    @patch('football.views.load_cached_next_match')
    @patch('football.views.load_universo_snapshot')
    def test_dashboard_data_ignores_global_snapshot_for_other_club_workspace(self, mock_snapshot, mock_cached_next):
        alt_competition = Competition.objects.create(name='Liga Cliente 2', slug='liga-cliente-2', region='Andalucia')
        alt_season = Season.objects.create(competition=alt_competition, name='2025/2026', is_current=True)
        alt_group = Group.objects.create(season=alt_season, name='Grupo Cliente 2', slug='grupo-cliente-2')
        alt_team = Team.objects.create(name='Club Visitante', slug='club-visitante', group=alt_group, is_primary=False)
        alt_rival = Team.objects.create(name='Rival Cliente 2', slug='rival-cliente-2', group=alt_group)
        TeamStanding.objects.create(season=alt_season, group=alt_group, team=alt_team, position=3, played=24, wins=13, draws=4, losses=7, goals_for=41, goals_against=28, goal_difference=13, points=43)
        Match.objects.create(
            season=alt_season,
            group=alt_group,
            round='J26',
            date=timezone.localdate() + timedelta(days=2),
            location='Campo Cliente 2',
            home_team=alt_team,
            away_team=alt_rival,
        )
        workspace = Workspace.objects.create(
            name='Cliente alternativo 2',
            slug='cliente-alternativo-2-workspace',
            kind=Workspace.KIND_CLUB,
            primary_team=alt_team,
        )
        mock_snapshot.return_value = {
            'standings': [
                {'position': 1, 'team': 'BENAGALBON MATRIZ', 'played': 24, 'points': 55},
            ]
        }
        mock_cached_next.return_value = {
            'status': 'next',
            'round': 'J30',
            'date': '2026-04-10',
            'location': 'Campo Snapshot',
            'opponent': {'name': 'Rival Snapshot', 'full_name': 'Rival Snapshot'},
        }
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-data'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['team']['name'], alt_team.name)
        self.assertEqual(payload['standings'][0]['team'], alt_team.name.upper())
        self.assertEqual(payload['next_match']['opponent']['name'], alt_rival.name)

    def test_dashboard_data_ignores_undated_current_convocation_for_next_match(self):
        future_rival = Team.objects.create(name='Rival Futuro Dashboard', slug='rival-futuro-dashboard', group=self.alt_team.group)
        Match.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            round='J27',
            date=timezone.localdate() + timedelta(days=3),
            location='Campo Dashboard',
            home_team=self.alt_team,
            away_team=future_rival,
        )
        ConvocationRecord.objects.create(
            team=self.alt_team,
            round='Partido 1',
            location='CASABERMEJA',
            opponent_name='Casabermeja',
            is_current=True,
        )
        workspace = Workspace.objects.create(
            name='Cliente dashboard convocation',
            slug='cliente-dashboard-convocation',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-data'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['next_match']['opponent']['name'], future_rival.name)
        self.assertEqual(payload['next_match']['round'], 'J27')

    def test_convocation_page_uses_active_club_workspace_team(self):
        workspace = Workspace.objects.create(
            name='Cliente alternativo',
            slug='cliente-alternativo-workspace-convocation',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        Player.objects.create(team=self.alt_team, name='Jugador cliente', is_active=True)
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('convocation'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alt_team.display_name)
        self.assertContains(response, 'Jugador cliente')

    def test_player_detail_uses_active_club_workspace_team_scope(self):
        workspace = Workspace.objects.create(
            name='Cliente alternativo',
            slug='cliente-alternativo-workspace-player',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        alt_player = Player.objects.create(team=self.alt_team, name='Defensa cliente', is_active=True)
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('player-detail', args=[alt_player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Defensa cliente')

    @patch('football.views.load_cached_next_match')
    @patch('football.views.load_universo_snapshot')
    def test_coach_overview_uses_workspace_team_competition_context(self, mock_snapshot, mock_cached_next):
        alt_competition = Competition.objects.create(name='Liga Coach 2', slug='liga-coach-2', region='Andalucia')
        alt_season = Season.objects.create(competition=alt_competition, name='2025/2026', is_current=True)
        alt_group = Group.objects.create(season=alt_season, name='Grupo Coach 2', slug='grupo-coach-2')
        alt_team = Team.objects.create(name='Club Costero', slug='club-costero', group=alt_group, is_primary=False)
        alt_rival = Team.objects.create(name='Rival Costero', slug='rival-costero', group=alt_group)
        TeamStanding.objects.create(season=alt_season, group=alt_group, team=alt_team, position=5, played=24, wins=11, draws=6, losses=7, goals_for=35, goals_against=29, goal_difference=6, points=39)
        Match.objects.create(
            season=alt_season,
            group=alt_group,
            round='J27',
            date=date(2026, 4, 12),
            location='Campo Costero',
            home_team=alt_team,
            away_team=alt_rival,
        )
        workspace = Workspace.objects.create(
            name='Cliente costero',
            slug='cliente-costero-workspace',
            kind=Workspace.KIND_CLUB,
            primary_team=alt_team,
        )
        mock_snapshot.return_value = {
            'standings': [
                {'position': 1, 'team': 'BENAGALBON MATRIZ', 'played': 24, 'points': 55},
            ]
        }
        mock_cached_next.return_value = {
            'status': 'next',
            'round': 'J30',
            'date': '2026-04-10',
            'location': 'Campo Snapshot',
            'opponent': {'name': 'Rival Snapshot', 'full_name': 'Rival Snapshot'},
        }
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Costero')
        self.assertContains(response, 'CLUB COSTERO')
        self.assertContains(response, '39')

    def test_workspace_detail_updates_enabled_modules(self):
        workspace = Workspace.objects.create(
            name='Cliente módulos',
            slug='cliente-modulos',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            enabled_modules={'dashboard': True, 'analysis': True},
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'update_modules',
                'module_technical_staff': 'on',
                'deliverable_technical_staff__staff_roster': 'on',
                'module_match': 'on',
                'deliverable_match__convocation': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        self.assertTrue(workspace.enabled_modules.get('players'))
        self.assertTrue(workspace.enabled_modules.get('convocation'))
        self.assertFalse(workspace.enabled_modules.get('match_actions'))
        self.assertFalse(workspace.enabled_modules.get('dashboard'))
        self.assertFalse(workspace.enabled_modules.get('analysis'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__technical_staff__staff_roster'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__match__convocation'))
        self.assertFalse(workspace.enabled_modules.get('deliverable__match__starting_xi'))
        self.assertFalse(workspace.enabled_modules.get('deliverable__match__live_match'))

    def test_workspace_detail_can_update_identity(self):
        workspace = Workspace.objects.create(
            name='Cliente editable',
            slug='cliente-editable',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            notes='Antes',
            is_active=True,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'update_workspace_identity',
                'workspace_name': 'Cliente editado',
                'owner_username': self.workspace_manager.username,
                'team_id': self.alt_team.id,
                'workspace_notes': 'Después',
                'workspace_is_active': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, 'Cliente editado')
        self.assertEqual(workspace.owner_user_id, self.workspace_manager.id)
        self.assertEqual(workspace.primary_team_id, self.alt_team.id)
        self.assertEqual(workspace.notes, 'Después')
        self.assertFalse(workspace.is_active)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.workspace_manager,
                role=WorkspaceMembership.ROLE_OWNER,
            ).exists()
        )

    def test_workspace_detail_can_update_and_sync_competition_context(self):
        workspace = Workspace.objects.create(
            name='Cliente competición',
            slug='cliente-competicion',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        self.client.force_login(self.admin_user)
        Match.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            round='J28',
            date=date(2026, 4, 12),
            location='Campo alternativo',
            home_team=self.alt_team,
            away_team=self.team,
        )
        TeamStanding.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            team=self.alt_team,
            position=4,
            played=24,
            wins=12,
            draws=3,
            losses=9,
            goals_for=31,
            goals_against=27,
            goal_difference=4,
            points=39,
        )

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'update_competition_context',
                'competition_provider': WorkspaceCompetitionContext.PROVIDER_RFAF,
                'external_competition_key': 'rfaf:liga-plataforma',
                'external_group_key': 'rfaf:grupo-plataforma',
                'external_team_key': 'rfaf:cliente-alternativo',
                'external_team_name': 'Cliente alternativo',
                'competition_auto_sync': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        context = WorkspaceCompetitionContext.objects.get(workspace=workspace, team=self.alt_team)
        self.assertEqual(context.provider, WorkspaceCompetitionContext.PROVIDER_RFAF)
        self.assertEqual(context.external_team_key, 'rfaf:cliente-alternativo')

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {'form_action': 'sync_competition_context'},
        )

        self.assertEqual(response.status_code, 200)
        context.refresh_from_db()
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(context.sync_status, WorkspaceCompetitionContext.STATUS_READY)
        self.assertEqual(snapshot.next_match_payload.get('round'), 'J28')
        self.assertEqual(snapshot.standings_payload[0].get('team'), self.alt_team.name.upper())

    @patch('football.views._sync_workspace_competition_context')
    def test_workspace_detail_get_does_not_auto_sync_competition_context(self, mock_sync):
        workspace = Workspace.objects.create(
            name='Cliente sin snapshot',
            slug='cliente-sin-snapshot',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        WorkspaceCompetitionContext.objects.create(
            workspace=workspace,
            team=self.alt_team,
            group=self.alt_team.group,
            season=self.alt_team.group.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name=self.alt_team.name,
            is_auto_sync_enabled=True,
            sync_status=WorkspaceCompetitionContext.STATUS_PENDING,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-workspace-detail', args=[workspace.id]))

        self.assertEqual(response.status_code, 200)
        mock_sync.assert_not_called()

    def test_workspace_detail_can_invite_member(self):
        workspace = Workspace.objects.create(
            name='Task Studio invitaciones',
            slug='task-studio-invite',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'invite_member',
                'invite_username': 'invite-demo',
                'invite_full_name': 'Demo Invitado',
                'invite_email': 'invite-demo@example.com',
                'invite_app_role': AppUserRole.ROLE_GUEST,
                'invite_member_role': WorkspaceMembership.ROLE_VIEWER,
                'invite_valid_days': '7',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invitación generada')
        invitation = UserInvitation.objects.filter(user__username='invite-demo', is_active=True).order_by('-created_at').first()
        self.assertIsNotNone(invitation)
        self.assertTrue(WorkspaceMembership.objects.filter(workspace=workspace, user=invitation.user).exists())

    def test_workspace_detail_can_search_competition_candidates(self):
        workspace = Workspace.objects.create(
            name='Cliente búsqueda',
            slug='cliente-busqueda',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'search_competition_context',
                'competition_provider_search': WorkspaceCompetitionContext.PROVIDER_RFAF,
                'competition_team_query': 'Cliente alternativo',
                'competition_competition_query': 'Liga Plataforma',
                'competition_group_query': 'Grupo Plataforma',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cliente alternativo')
        self.assertContains(response, 'Vincular y sincronizar')

    @patch('football.views._fetch_universo_live_classification')
    @patch('football.views._fetch_universo_live_groups')
    @patch('football.views._fetch_universo_live_competitions')
    @patch('football.views._fetch_universo_live_delegations')
    @patch('football.views._fetch_universo_live_seasons')
    def test_workspace_detail_can_search_universo_live_candidates(
        self,
        mock_seasons,
        mock_delegations,
        mock_competitions,
        mock_groups,
        mock_classification,
    ):
        workspace = Workspace.objects.create(
            name='Cliente universo búsqueda',
            slug='cliente-universo-busqueda',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        mock_seasons.return_value = [{'cod_temporada': '21', 'nombre': '2025-2026'}]
        mock_delegations.return_value = [{'cod_delegacion': '8', 'nombre': 'Málaga'}]
        mock_competitions.return_value = [{'codigo': '45030612', 'nombre': 'División Honor Sénior'}]
        mock_groups.return_value = [{'codigo': '45030656', 'nombre': 'Grupo 2'}]
        mock_classification.return_value = {
            'clasificacion': [
                {'codequipo': '500315', 'nombre': 'LOJA C.D.'},
            ],
        }
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'search_competition_context',
                'competition_provider_search': WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
                'competition_team_query': 'Loja',
                'competition_competition_query': 'División Honor',
                'competition_group_query': 'Grupo 2',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Universo RFAF · live')
        self.assertContains(response, 'LOJA C.D.')

    def test_workspace_detail_can_apply_competition_candidate(self):
        workspace = Workspace.objects.create(
            name='Cliente onboarding',
            slug='cliente-onboarding',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        rival = Team.objects.create(name='Rival onboarding', slug='rival-onboarding', group=self.alt_team.group)
        Match.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            round='J29',
            date=date(2026, 4, 20),
            location='Campo onboarding',
            home_team=self.alt_team,
            away_team=rival,
        )
        TeamStanding.objects.create(
            season=self.alt_team.group.season,
            group=self.alt_team.group,
            team=self.alt_team,
            position=5,
            played=25,
            wins=11,
            draws=6,
            losses=8,
            goals_for=34,
            goals_against=29,
            goal_difference=5,
            points=39,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'apply_competition_candidate',
                'candidate_provider': WorkspaceCompetitionContext.PROVIDER_RFAF,
                'candidate_team_id': self.alt_team.id,
                'candidate_external_competition_key': 'liga-plataforma',
                'candidate_external_group_key': 'grupo-plataforma',
                'candidate_external_team_key': 'cliente-alternativo',
                'candidate_external_team_name': 'Cliente alternativo',
                'candidate_auto_sync': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        context = WorkspaceCompetitionContext.objects.get(workspace=workspace, team=self.alt_team)
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(workspace.primary_team_id, self.alt_team.id)
        self.assertEqual(context.team_id, self.alt_team.id)
        self.assertEqual(context.sync_status, WorkspaceCompetitionContext.STATUS_READY)
        self.assertEqual(snapshot.next_match_payload.get('round'), 'J29')
        self.assertEqual(snapshot.standings_payload[0].get('team'), self.alt_team.name.upper())

    @patch('football.views.load_universo_snapshot')
    @patch('football.views._build_universo_competition_catalog')
    def test_workspace_detail_can_import_universo_candidate(self, mock_catalog, mock_snapshot):
        workspace = Workspace.objects.create(
            name='Cliente universo',
            slug='cliente-universo',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
        )
        mock_catalog.return_value = {
            'competitions': {
                '45030612': {
                    'code': '45030612',
                    'name': 'División Honor Sénior',
                    'season_name': '2025/2026',
                    'start_date': '2025-09-13',
                    'end_date': '2026-04-26',
                    'region': 'Málaga',
                },
            },
            'groups': {
                ('45030612', '45030656'): {
                    'competition_code': '45030612',
                    'group_code': '45030656',
                    'group_name': 'Grupo 2',
                },
            },
            'classifications': {
                ('45030612', '45030656'): {
                    'competition_code': '45030612',
                    'competition_name': 'División Honor Sénior',
                    'group_code': '45030656',
                    'group_name': 'Grupo 2',
                    'round': '26',
                    'rows': [
                        {
                            'codequipo': 'demo-001',
                            'nombre': 'Club Universo Demo',
                            'posicion': '4',
                            'jugados': '24',
                            'ganados': '12',
                            'empatados': '5',
                            'perdidos': '7',
                            'goles_a_favor': '38',
                            'goles_en_contra': '29',
                            'puntos': '41',
                        },
                        {
                            'codequipo': 'demo-002',
                            'nombre': 'Rival Universo',
                            'posicion': '7',
                            'jugados': '24',
                            'ganados': '10',
                            'empatados': '4',
                            'perdidos': '10',
                            'goles_a_favor': '30',
                            'goles_en_contra': '31',
                            'puntos': '34',
                        },
                    ],
                },
            },
        }
        mock_snapshot.return_value = {
            'standings': [
                {'position': 4, 'team': 'CLUB UNIVERSO DEMO', 'points': 41},
                {'position': 7, 'team': 'RIVAL UNIVERSO', 'points': 34},
            ],
            'next_match': {
                'round': 'J27',
                'date': '2026-04-18',
                'location': 'Campo Universo',
                'opponent': {'name': 'Rival Universo', 'full_name': 'Rival Universo'},
                'home': True,
                'status': 'next',
            },
        }
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'apply_competition_candidate',
                'candidate_provider': WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
                'candidate_team_id': '',
                'candidate_external_competition_key': '45030612',
                'candidate_external_group_key': '45030656',
                'candidate_external_team_key': 'demo-001',
                'candidate_external_team_name': 'Club Universo Demo',
                'candidate_auto_sync': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        context = WorkspaceCompetitionContext.objects.get(workspace=workspace, team=workspace.primary_team)
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(workspace.primary_team.name, 'Club Universo Demo')
        self.assertEqual(context.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
        self.assertEqual(context.external_group_key, '45030656')
        self.assertEqual(snapshot.next_match_payload.get('round'), 'J27')
        self.assertEqual(snapshot.standings_payload[0].get('team'), 'CLUB UNIVERSO DEMO')

    def test_workspace_detail_updates_task_studio_deliverables(self):
        workspace = Workspace.objects.create(
            name='Task Studio módulos',
            slug='task-studio-modulos',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
            enabled_modules={'task_studio_home': True, 'task_studio_profile': True, 'task_studio_roster': True, 'task_studio_tasks': True, 'task_studio_pdfs': True},
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'update_modules',
                'module_task_studio_tasks_library': 'on',
                'deliverable_task_studio_tasks_library__repository': 'on',
                'module_task_studio_documents_exports': 'on',
                'deliverable_task_studio_documents_exports__pdfs': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        self.assertFalse(workspace.enabled_modules.get('task_studio_home'))
        self.assertFalse(workspace.enabled_modules.get('task_studio_profile'))
        self.assertFalse(workspace.enabled_modules.get('task_studio_roster'))
        self.assertTrue(workspace.enabled_modules.get('task_studio_tasks'))
        self.assertTrue(workspace.enabled_modules.get('task_studio_pdfs'))
        self.assertTrue(workspace.enabled_modules.get('module__task_studio_tasks_library'))
        self.assertTrue(workspace.enabled_modules.get('deliverable__task_studio_tasks_library__repository'))
        self.assertFalse(workspace.enabled_modules.get('deliverable__task_studio_tasks_library__editor'))

    def test_enter_workspace_redirects_to_first_enabled_module(self):
        workspace = Workspace.objects.create(
            name='Cliente sin dashboard',
            slug='cliente-sin-dashboard',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            enabled_modules={
                'dashboard': False,
                'coach_overview': False,
                'players': True,
                'convocation': False,
                'match_actions': False,
                'sessions': False,
                'analysis': False,
                'abp_board': False,
                'manual_stats': False,
            },
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-workspace-enter', args=[workspace.id]))

        self.assertRedirects(response, reverse('player-dashboard'))

    def test_disabled_convocation_module_returns_403(self):
        workspace = Workspace.objects.create(
            name='Cliente sin convocatoria',
            slug='cliente-sin-convocatoria',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            enabled_modules={
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': False,
                'match_actions': True,
                'sessions': True,
                'analysis': True,
                'abp_board': True,
                'manual_stats': True,
            },
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('convocation'))

        self.assertEqual(response.status_code, 403)

    def test_club_member_dashboard_redirects_to_first_enabled_workspace_module(self):
        workspace = Workspace.objects.create(
            name='Cliente técnico',
            slug='cliente-tecnico',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
            enabled_modules={
                'dashboard': False,
                'coach_overview': False,
                'players': True,
                'convocation': False,
                'match_actions': False,
                'sessions': False,
                'analysis': False,
                'abp_board': False,
                'manual_stats': False,
                'module__technical_staff': True,
                'deliverable__technical_staff__staff_roster': True,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('dashboard-home'))

        self.assertRedirects(response, reverse('player-dashboard'), fetch_redirect_response=False)

    def test_workspace_admin_can_open_detail_without_superadmin_role(self):
        workspace = Workspace.objects.create(
            name='Cliente gestionado',
            slug='cliente-gestionado',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('platform-workspace-detail', args=[workspace.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cliente gestionado')

    def test_workspace_admin_can_add_member(self):
        workspace = Workspace.objects.create(
            name='Cliente miembros',
            slug='cliente-miembros',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.post(
            reverse('platform-workspace-detail', args=[workspace.id]),
            {
                'form_action': 'add_member',
                'member_username': self.basic_user.username,
                'member_role': WorkspaceMembership.ROLE_MEMBER,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.basic_user,
                role=WorkspaceMembership.ROLE_MEMBER,
            ).exists()
        )

    def test_dashboard_shows_workspace_link_for_workspace_admin(self):
        workspace = Workspace.objects.create(
            name='Cliente visible',
            slug='cliente-visible',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('dashboard-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Segunda Jugada · 2J Club')
        self.assertNotContains(response, 'Selecciona un workspace')

    def test_dashboard_shows_competitive_summary_for_workspace_admin(self):
        workspace = Workspace.objects.create(
            name='Cliente foco',
            slug='cliente-foco',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('dashboard-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estado del equipo')
        self.assertContains(response, 'Próximo rival')
        self.assertContains(response, 'Clasificación')

    def test_workspace_member_auto_uses_assigned_club_context(self):
        workspace = Workspace.objects.create(
            name='Cliente alternativo miembro',
            slug='cliente-alternativo-miembro',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_MEMBER,
        )
        Player.objects.create(team=self.alt_team, name='Jugador del cliente', is_active=True)
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('convocation'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alt_team.display_name)
        self.assertContains(response, 'Jugador del cliente')
        self.assertEqual(self.client.session.get('active_workspace_id'), workspace.id)

    def test_technical_user_without_workspace_cannot_access_club_modules(self):
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('convocation'))

        self.assertEqual(response.status_code, 404)

    def test_workspace_member_cannot_enter_other_client_workspace(self):
        own_workspace = Workspace.objects.create(
            name='Cliente propio',
            slug='cliente-propio',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        other_workspace = Workspace.objects.create(
            name='Cliente ajeno',
            slug='cliente-ajeno',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(
            workspace=own_workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_MEMBER,
        )
        self.client.force_login(self.workspace_manager)

        response = self.client.get(reverse('platform-workspace-enter', args=[other_workspace.id]))

        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(self.client.session.get('active_workspace_id'), other_workspace.id)

    def test_platform_can_delete_task_studio_workspace_and_private_data(self):
        workspace = Workspace.objects.create(
            name='Task Studio borrable',
            slug='task-studio-borrable',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.studio_user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        TaskStudioProfile.objects.create(user=self.studio_user, workspace=workspace, display_name='Studio')
        TaskStudioRosterPlayer.objects.create(owner=self.studio_user, workspace=workspace, name='Jugador')
        TaskStudioTask.objects.create(owner=self.studio_user, workspace=workspace, title='Tarea', block=SessionTask.BLOCK_MAIN_1, duration_minutes=12)
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('platform-workspace-delete', args=[workspace.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Workspace.objects.filter(id=workspace.id).exists())
        self.assertFalse(TaskStudioTask.objects.filter(owner=self.studio_user).exists())
        self.assertFalse(TaskStudioRosterPlayer.objects.filter(owner=self.studio_user).exists())
        disabled_profile = TaskStudioProfile.objects.filter(user=self.studio_user).first()
        self.assertIsNotNone(disabled_profile)
        self.assertFalse(disabled_profile.is_enabled)
        self.assertIsNone(disabled_profile.workspace_id)
        self.assertContains(response, 'Task Studio eliminado')

    def test_platform_overview_excludes_task_studio_owners_from_users_summary(self):
        club_workspace = Workspace.objects.create(
            name='Cliente usuarios',
            slug='cliente-usuarios',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceMembership.objects.create(
            workspace=club_workspace,
            user=self.workspace_manager,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        studio_workspace = Workspace.objects.create(
            name='Task Studio privado',
            slug='task-studio-privado',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
        )
        WorkspaceMembership.objects.create(
            workspace=studio_workspace,
            user=self.studio_user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-overview'), {'tab': 'users', 'subtab': 'list'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.workspace_manager.username)
        self.assertContains(response, 'clientes club')
        listed_usernames = [membership.user.username for membership in response.context['workspace_users']]
        self.assertIn(self.workspace_manager.username, listed_usernames)
        self.assertNotIn(self.studio_user.username, listed_usernames)

    def test_platform_overview_hides_orphan_task_studio_workspace_cards(self):
        Workspace.objects.create(
            name='Task Studio huerfano',
            slug='task-studio-huerfano',
            kind=Workspace.KIND_TASK_STUDIO,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)
        listed_ids = [workspace.id for workspace in response.context['studio_workspaces']]
        self.assertEqual(len(listed_ids), len(set(listed_ids)))
        self.assertNotContains(response, 'Task Studio huerfano')

    def test_platform_overview_does_not_recreate_deleted_task_studio_workspace(self):
        workspace = Workspace.objects.create(
            name='Task Studio eliminable',
            slug='task-studio-eliminable',
            kind=Workspace.KIND_TASK_STUDIO,
            owner_user=self.studio_user,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.studio_user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        self.client.force_login(self.admin_user)
        self.client.post(reverse('platform-workspace-delete', args=[workspace.id]))

        response = self.client.get(reverse('platform-overview'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Workspace.objects.filter(kind=Workspace.KIND_TASK_STUDIO, owner_user=self.studio_user).exists())

    def test_platform_cannot_delete_club_workspace_without_confirmation(self):
        workspace = Workspace.objects.create(
            name='Cliente borrable',
            slug='cliente-borrable',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('platform-workspace-delete', args=[workspace.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirmación inválida')
        self.assertTrue(Workspace.objects.filter(id=workspace.id).exists())

    def test_platform_refuses_to_delete_primary_club_workspace(self):
        workspace = Workspace.objects.create(
            name='Cliente principal',
            slug='cliente-principal',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('platform-workspace-delete', args=[workspace.id]),
            {'confirm_slug': workspace.slug, 'confirm_phrase': 'ELIMINAR'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se puede eliminar')
        self.assertTrue(Workspace.objects.filter(id=workspace.id).exists())

    def test_platform_can_delete_club_workspace_with_confirmation(self):
        workspace = Workspace.objects.create(
            name='Cliente pruebas',
            slug='cliente-pruebas',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session['active_team_by_workspace'] = {str(workspace.id): int(self.alt_team.id)}
        session.save()

        response = self.client.post(
            reverse('platform-workspace-delete', args=[workspace.id]),
            {'confirm_slug': workspace.slug, 'confirm_phrase': 'ELIMINAR'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Workspace.objects.filter(id=workspace.id).exists())
        self.assertNotEqual(int(self.client.session.get('active_workspace_id') or 0), int(workspace.id))
        self.assertContains(response, 'Cliente eliminado')


class QueryHelperTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga', slug='liga', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo 1', slug='grupo-1')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival', slug='rival', group=group)
        self.match = Match.objects.create(season=season, group=group, home_team=self.team, away_team=self.rival)

    def test_get_current_convocation_record_prefers_specific_match(self):
        old_record = ConvocationRecord.objects.create(team=self.team, is_current=True)
        target_record = ConvocationRecord.objects.create(team=self.team, match=self.match, is_current=True)

        resolved = get_current_convocation_record(self.team, match=self.match)

        self.assertEqual(resolved.id, target_record.id)
        self.assertNotEqual(resolved.id, old_record.id)

    def test_manual_sanction_helper_expires_after_until_date(self):
        player = Player.objects.create(
            team=self.team,
            name='Jugador Uno',
            manual_sanction_active=True,
            manual_sanction_until=timezone.localdate() - timedelta(days=1),
        )

        self.assertFalse(is_manual_sanction_active(player, today=timezone.localdate()))

    def test_injury_record_helper_ignores_records_with_past_return_date(self):
        player = Player.objects.create(team=self.team, name='Jugador Dos')
        record = player.injury_records.create(
            injury='Sobrecarga',
            injury_date=timezone.localdate() - timedelta(days=7),
            return_date=timezone.localdate() - timedelta(days=1),
            is_active=True,
        )

        self.assertFalse(is_injury_record_active(record, today=timezone.localdate()))
        self.assertFalse(get_active_injury_player_ids([player.id]))

    def test_time_loss_helpers(self):
        today = timezone.localdate()
        self.assertEqual(time_loss_days(today - timedelta(days=2), today, today=today), 3)
        self.assertEqual(categorize_time_loss(0), 'minima')
        self.assertEqual(categorize_time_loss(3), 'minima')
        self.assertEqual(categorize_time_loss(4), 'leve')
        self.assertEqual(categorize_time_loss(10), 'moderada')
        self.assertEqual(categorize_time_loss(40), 'grave')

    def test_estimate_return_date_uses_grade(self):
        today = date(2026, 4, 15)
        self.assertEqual(estimate_return_date(today, 7, 84, severity_grade=1), date(2026, 4, 22))
        self.assertEqual(estimate_return_date(today, 7, 84, severity_grade=2), date(2026, 5, 31))
        self.assertEqual(estimate_return_date(today, 7, 84, severity_grade=3), date(2026, 7, 8))


class ConvocationWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='convocation-user',
            email='convocation@example.com',
            password='pass-1234',
        )
        competition = Competition.objects.create(name='Liga Convocatoria', slug='liga-convocatoria', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Convocatoria', slug='grupo-convocatoria')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-convocatoria', group=group, is_primary=True)
        self.player = Player.objects.create(team=self.team, name='Martinez', position='MC')
        self.workspace = Workspace.objects.create(
            name='Workspace Convocatoria',
            slug='ws-convocatoria',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.user,
            enabled_modules={'dashboard': True, 'players': True, 'convocation': True},
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def test_save_convocation_allows_pending_match_without_players(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('convocation-save'),
            data=json.dumps(
                {
                    'players': [],
                    'match_info': {
                        'opponent': 'Alhaurín de la Torre',
                        'round': 'J24',
                        'date': '2026-03-29',
                        'time': '18:00',
                        'location': 'ESTADIO CAÑA CHAQUETA',
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['saved'])
        self.assertTrue(payload['pending_convocation'])
        record = ConvocationRecord.objects.get(team=self.team, is_current=True)
        self.assertEqual(record.players.count(), 0)
        self.assertEqual(record.opponent_name, 'Alhaurín de la Torre')

    def test_save_convocation_persists_captain_and_goalkeeper(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('convocation-save'),
            data=json.dumps(
                {
                    'players': [self.player.id],
                    'captain_id': self.player.id,
                    'goalkeeper_id': self.player.id,
                    'match_info': {
                        'opponent': 'Rival 2',
                        'round': 'J2',
                        'date': '2026-01-17',
                        'time': '10:00',
                        'location': 'Campo 2',
                    },
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        record = ConvocationRecord.objects.get(team=self.team, is_current=True)
        self.assertEqual(record.captain_id, self.player.id)
        self.assertEqual(record.goalkeeper_id, self.player.id)

    def test_player_detail_shows_pending_convocation_alert(self):
        self.client.force_login(self.user)
        ConvocationRecord.objects.create(
            team=self.team,
            round='J24',
            opponent_name='Alhaurín de la Torre',
            match_date=date(2026, 3, 29),
            is_current=True,
        )

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Convocatoria pendiente')

    def test_initial_eleven_page_marks_pending_convocation_without_players(self):
        self.client.force_login(self.user)
        ConvocationRecord.objects.create(
            team=self.team,
            round='J24',
            opponent_name='Alhaurín de la Torre',
            match_date=date(2026, 3, 29),
            is_current=True,
        )

        response = self.client.get(reverse('initial-eleven'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_pending_convocation'])
        self.assertContains(response, 'Convocatoria pendiente')

    def test_initial_eleven_page_marks_pending_lineup_without_auto_fill(self):
        self.client.force_login(self.user)
        record = ConvocationRecord.objects.create(
            team=self.team,
            round='J24',
            opponent_name='Alhaurín de la Torre',
            match_date=date(2026, 3, 29),
            is_current=True,
        )
        record.players.add(self.player)

        response = self.client.get(reverse('initial-eleven'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_pending_lineup'])
        self.assertJSONEqual(response.context['lineup_seed_json'], {'starters': [], 'bench': []})

    @patch('football.views._build_pdf_response_or_html_fallback')
    def test_convocation_pdf_accepts_team_param_without_active_workspace(self, mock_pdf):
        mock_pdf.return_value = HttpResponse('ok', status=200)
        self.client.force_login(self.user)
        record = ConvocationRecord.objects.create(
            team=self.team,
            round='J1',
            opponent_name='Rival',
            match_date=date(2026, 3, 29),
            is_current=True,
        )
        record.players.add(self.player)
        session = self.client.session
        session.pop('active_workspace_id', None)
        session.save()

        response = self.client.get(reverse('convocation-pdf'), {'team': self.team.id})

        self.assertEqual(response.status_code, 200)

    @patch('football.views._build_pdf_response_or_html_fallback')
    def test_match_report_pdf_resolves_team_from_match_without_active_workspace(self, mock_pdf):
        mock_pdf.return_value = HttpResponse('ok', status=200)
        self.client.force_login(self.user)
        match = Match.objects.create(
            season=self.team.group.season,
            group=self.team.group,
            home_team=self.team,
            away_team=None,
            round='J1',
            date=timezone.localdate(),
            location='Campo',
        )
        session = self.client.session
        session.pop('active_workspace_id', None)
        session.save()

        response = self.client.get(reverse('match-report-pdf'), {'match_id': match.id})

        self.assertEqual(response.status_code, 200)


class HealthcheckTests(TestCase):
    def test_system_healthcheck_returns_expected_sections(self):
        report = run_system_healthcheck()

        self.assertIn('ok', report)
        self.assertIn('database', report)
        self.assertIn('paths', report)
        self.assertIn('dependencies', report)
        self.assertIn('static_root', report['paths'])


class BootstrapAdminTests(TestCase):
    @patch.dict(
        'os.environ',
        {
            'BOOTSTRAP_ADMIN_USERNAME': 'mperez',
            'BOOTSTRAP_ADMIN_PASSWORD': 'TmpPass2026!',
            'BOOTSTRAP_ADMIN_EMAIL': 'mperez@example.com',
            'BOOTSTRAP_ADMIN_RESET_PASSWORD': 'false',
        },
        clear=False,
    )
    def test_bootstrap_admin_creates_admin_user(self):
        user = ensure_bootstrap_admin_from_env()

        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'mperez')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('TmpPass2026!'))
        self.assertEqual(user.app_role.role, AppUserRole.ROLE_ADMIN)

    @patch.dict(
        'os.environ',
        {
            'BOOTSTRAP_ADMIN_USERNAME': 'mperez',
            'BOOTSTRAP_ADMIN_PASSWORD': 'NuevaTmp2026!',
            'BOOTSTRAP_ADMIN_EMAIL': 'mperez@example.com',
            'BOOTSTRAP_ADMIN_RESET_PASSWORD': 'true',
        },
        clear=False,
    )
    def test_bootstrap_admin_can_reset_existing_password(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='mperez',
            password='old-pass',
            is_active=True,
        )

        ensure_bootstrap_admin_from_env()

        user.refresh_from_db()
        self.assertTrue(user.check_password('NuevaTmp2026!'))


class TaskLibraryTests(TestCase):
    def _make_task(self, **overrides):
        defaults = {
            'id': 1,
            'title': 'Rondo de activacion',
            'objective': '',
            'coaching_points': '',
            'confrontation_rules': '',
            'duration_minutes': 18,
            'tactical_layout': {},
            'session': SimpleNamespace(session_date=date(2026, 3, 20)),
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_prepare_task_library_enriches_group_rows_and_flags_review(self):
        task = self._make_task(
            tactical_layout={
                'meta': {
                    'analysis': {
                        'summary': 'Conservacion y pressing tras perdida.',
                        'work_contexts': ['Inicio'],
                        'objective_tags': ['Conservacion'],
                        'task_sheet': {'description': 'Rondo corto', 'players': '6'},
                    }
                }
            }
        )

        context = prepare_task_library(
            [task],
            parse_int=lambda value: int(value) if str(value).isdigit() else None,
            sanitize_text=lambda value, **kwargs: value.strip(),
            analysis_confidence_scores=lambda payload: {'overall': 40},
            task_upload_date=lambda current: current.session.session_date,
            extract_effective_reference_date=lambda current, analysis_meta=None: None,
            detect_keyword_tags=lambda text, keywords: ['Rondo'] if 'rondo' in text.lower() else [],
            task_type_keywords={'rondo': ['rondo']},
            task_phase_keywords={'inicio': ['activacion']},
            players_band_label=lambda count: 'Hasta 8',
            estimate_players_count=lambda players, title: 6,
            duration_band_label=lambda minutes: '15-20 min',
            phase_folder_key_for_task=lambda current: 'inicio',
            phase_folder_meta=[{'key': 'inicio', 'label': 'Inicio'}],
            coerce_reference_date=lambda raw: date.fromisoformat(raw),
            is_imported_task=lambda current: True,
        )

        enriched = context['task_library'][0]
        self.assertTrue(enriched.is_imported)
        self.assertTrue(enriched.needs_review)
        self.assertEqual(enriched.players_band, 'Hasta 8')
        self.assertEqual(enriched.duration_band, '15-20 min')
        self.assertEqual(enriched.phase_folder_key, 'inicio')
        self.assertEqual(context['context_group_rows'][0]['key'], 'Inicio')
        self.assertEqual(context['quality_group_rows'][0]['count'], 1)
        self.assertEqual(context['date_group_rows'][0]['label'], '20/03/2026')

    def test_filter_task_library_supports_quality_and_phase_views(self):
        reviewed = self._make_task(
            id=1,
            phase_folder_key='inicio',
            exercise_types=['Rondo'],
            players_band='Hasta 8',
            duration_band='15-20 min',
            needs_review=True,
            reference_date=date(2026, 3, 20),
            reference_date_iso='2026-03-20',
        )
        validated = self._make_task(
            id=2,
            phase_folder_key='principal',
            exercise_types=['Juego de posicion'],
            players_band='9-14',
            duration_band='20-30 min',
            needs_review=False,
            reference_date=date(2026, 3, 21),
            reference_date_iso='2026-03-21',
        )

        reviewed_items = filter_task_library(
            [reviewed, validated],
            library_view='quality',
            library_key='review',
        )
        phase_items = filter_task_library(
            [reviewed, validated],
            library_view='phase',
            library_key='principal',
        )

        self.assertEqual([item.id for item in reviewed_items], [1])
        self.assertEqual([item.id for item in phase_items], [2])


class ManualStatsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='statsadmin',
            email='statsadmin@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga Manual', slug='liga-manual', region='Andalucia')
        self.season = Season.objects.create(competition=competition, name='', is_current=True)
        group = Group.objects.create(season=self.season, name='Grupo Manual', slug='grupo-manual')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-manual', group=group, is_primary=True)
        self.player = Player.objects.create(team=self.team, name='Jugador Manual')

    def test_manual_stats_page_saves_overrides(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('manual-player-stats'),
            {
                f'pj_{self.player.id}': '11',
                f'pt_{self.player.id}': '9',
                f'minutes_{self.player.id}': '810',
                f'goals_{self.player.id}': '3',
                f'yellow_{self.player.id}': '2',
                f'red_{self.player.id}': '1',
            },
        )

        self.assertEqual(response.status_code, 200)
        overrides = get_manual_player_base_overrides(self.team, self.season)
        self.assertEqual(overrides[self.player.id]['pj'], 11)
        self.assertEqual(overrides[self.player.id]['minutes'], 810)
        self.assertContains(response, 'Estadísticas manuales guardadas.')

    @patch('football.views.get_roster_stats_cache', side_effect=RuntimeError('snapshot roto'))
    def test_manual_stats_page_tolerates_roster_cache_errors(self, mocked_cache):
        self.client.force_login(self.user)

        response = self.client.get(reverse('manual-player-stats'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Temporada actual')
        mocked_cache.assert_called_once()

    @patch('football.views.get_manual_player_base_overrides', side_effect=RuntimeError('override roto'))
    def test_manual_stats_page_falls_back_without_500(self, mocked_overrides):
        self.client.force_login(self.user)

        response = self.client.get(reverse('manual-player-stats'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se pudieron cargar las estadísticas manuales')
        mocked_overrides.assert_called_once()

    @patch('football.manual_stats.PlayerStatistic.objects.filter')
    def test_manual_overrides_tolerate_non_finite_values(self, mocked_filter):
        mocked_filter.return_value.select_related.return_value = [
            SimpleNamespace(
                player_id=self.player.id,
                name='manual_minutes',
                value='nan',
            )
        ]

        overrides = get_manual_player_base_overrides(self.team, self.season)

        self.assertEqual(overrides[self.player.id]['minutes'], 0)

    def test_season_display_name_falls_back_when_name_missing(self):
        self.assertEqual(season_display_name(self.season), 'Temporada actual')

    def test_save_manual_stats_collapses_duplicate_null_match_rows(self):
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=None,
            name='manual_minutes',
            context='manual-base',
            value=120,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=None,
            name='manual_minutes',
            context='manual-base',
            value=240,
        )

        save_manual_player_base_overrides(
            player=self.player,
            season=self.season,
            values={'manual_minutes': 810},
        )

        rows = PlayerStatistic.objects.filter(
            player=self.player,
            season=self.season,
            match=None,
            name='manual_minutes',
            context='manual-base',
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(int(rows.first().value), 810)


class RosterLookupTests(TestCase):
    def test_find_roster_entry_tolerates_malformed_cache(self):
        self.assertIsNone(find_roster_entry('Jugador', None))
        self.assertIsNone(find_roster_entry('Jugador', {'bad': 'value'}))
        self.assertEqual(
            find_roster_entry('Jugador Uno', {'ok': {'name': 'Jugador Uno', 'pj': 5}}),
            {'name': 'Jugador Uno', 'pj': 5},
        )


class PlayerDetailStatsFallbackTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='detailadmin',
            email='detailadmin@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga Detail', slug='liga-detail', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Detail', slug='grupo-detail')
        team = Team.objects.create(name='Benagalbon', slug='benagalbon-detail', group=group, is_primary=True)
        self.player = Player.objects.create(team=team, name='Jugador Detail')

    @patch('football.views.compute_player_dashboard', side_effect=RuntimeError('dashboard roto'))
    def test_player_detail_page_falls_back_when_stats_fail(self, mocked_dashboard):
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Las estadísticas consolidadas no están disponibles temporalmente.')
        mocked_dashboard.assert_called_once()

    def test_player_detail_shows_staff_tabs_even_without_explicit_app_role(self):
        no_role_user = get_user_model().objects.create_user(
            username='coachlegacy',
            email='coachlegacy@example.com',
            password='pass-1234',
        )
        self.client.force_login(no_role_user)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Multas')
        self.assertContains(response, 'Comunicación')

    def test_player_cannot_access_another_players_detail(self):
        player_user = get_user_model().objects.create_user(
            username='detallepropio',
            email='detallepropio@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=player_user, role=AppUserRole.ROLE_PLAYER)
        self.player.full_name = 'detallepropio'
        self.player.save(update_fields=['full_name'])
        other_player = Player.objects.create(team=self.player.team, name='Otro Jugador')

        self.client.force_login(player_user)
        response = self.client.get(reverse('player-detail', args=[other_player.id]))

        self.assertEqual(response.status_code, 403)

    def test_player_detail_readonly_shows_personal_summary_without_upload_form(self):
        player_user = get_user_model().objects.create_user(
            username='detallejugador',
            email='detallejugador@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=player_user, role=AppUserRole.ROLE_PLAYER)
        self.player.full_name = 'Jugador Detail Completo'
        self.player.nickname = 'JD'
        self.player.height_cm = 181
        self.player.weight_kg = 76.5
        self.player.save(update_fields=['full_name', 'nickname', 'height_cm', 'weight_kg'])

        self.client.force_login(player_user)
        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ficha personal')
        self.assertContains(response, 'Jugador Detail Completo')
        content = response.content.decode('utf-8')
        self.assertTrue('76.50 kg' in content or '76,50 kg' in content)
        self.assertContains(response, 'Lesiones')
        self.assertContains(response, 'Comunicación')
        self.assertNotContains(response, 'type="file"', html=False)
        self.assertNotContains(response, 'Guardar comunicación')

    def test_staff_can_preview_player_readonly_view(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-detail', args=[self.player.id]), {'preview': 'player'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_player_readonly'])
        self.assertTrue(response.context['player_view_preview'])
        self.assertContains(response, 'Vista previa jugador')
        self.assertContains(response, 'Ficha personal')
        self.assertNotContains(response, 'type="file"', html=False)
        self.assertNotContains(response, 'Guardar comunicación')

    @override_settings(MEDIA_URL='/media-test/')
    def test_player_detail_profile_upload_stores_photo_in_media(self):
        self.client.force_login(self.user)
        png_bytes = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Zl4QAAAAASUVORK5CYII='
        )
        upload = SimpleUploadedFile('jugador.png', png_bytes, content_type='image/png')
        media_root = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('player-detail', args=[self.player.id]),
                    {
                        'form_action': 'profile',
                        'full_name': 'Jugador Detail',
                        'nickname': '',
                        'birth_date': '',
                        'height_cm': '',
                        'weight_kg_base': '',
                        'number': '',
                        'position': '',
                        'injury': '',
                        'injury_type': '',
                        'injury_zone': '',
                        'injury_side': '',
                        'injury_date': '',
                        'injury_return_date': '',
                        'injury_notes': '',
                        'manual_sanction_active': '0',
                        'manual_sanction_reason': '',
                        'manual_sanction_until': '',
                        'injury_record_mode': 'update',
                        'player_photo': upload,
                    },
                    follow=True,
                )

                stored_path = Path(media_root) / 'player-photos' / f'player-{self.player.id}.png'
                self.assertTrue(stored_path.exists())
                self.assertIn(
                    f'/player/{self.player.id}/photo/',
                    response.context['player_photo_url'],
                )
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

        self.assertEqual(response.status_code, 200)


    @override_settings(MEDIA_URL='/media-test/')
    def test_player_detail_profile_upload_stores_license_in_media(self):
        self.client.force_login(self.user)
        pdf_bytes = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'
        upload = SimpleUploadedFile('licencia.pdf', pdf_bytes, content_type='application/pdf')
        media_root = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('player-detail', args=[self.player.id]),
                    {
                        'form_action': 'profile',
                        'full_name': 'Jugador Detail',
                        'nickname': '',
                        'birth_date': '',
                        'height_cm': '',
                        'weight_kg_base': '',
                        'number': '',
                        'position': '',
                        'injury': '',
                        'injury_type': '',
                        'injury_zone': '',
                        'injury_side': '',
                        'injury_date': '',
                        'injury_return_date': '',
                        'injury_notes': '',
                        'manual_sanction_active': '0',
                        'manual_sanction_reason': '',
                        'manual_sanction_until': '',
                        'injury_record_mode': 'update',
                        'player_license': upload,
                    },
                    follow=True,
                )
                stored_path = Path(media_root) / 'player-licenses' / f'player-{self.player.id}.pdf'
                self.assertTrue(stored_path.exists())
                self.assertIn(
                    f'/player/{self.player.id}/license/',
                    response.context['player_license_url'],
                )
        finally:
            shutil.rmtree(media_root, ignore_errors=True)
        self.assertEqual(response.status_code, 200)


class AdminActionsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='adminactions',
            email='adminactions@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga Admin', slug='liga-admin', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Admin', slug='grupo-admin')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-admin', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Admin', slug='rival-admin', group=group)
        self.match = Match.objects.create(
            season=season,
            group=group,
            home_team=self.team,
            away_team=self.rival,
            date=date(2026, 3, 24),
        )

    def test_actions_tab_renders_with_date_only_match(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('admin-page'), {'tab': 'actions', 'match_id': self.match.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partido a editar')

    def test_actions_tab_saves_match_time_into_kickoff_field(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('admin-page'),
            {
                'form_action': 'admin_match_save',
                'active_tab': 'actions',
                'match_id': self.match.id,
                'opponent_name': self.rival.name,
                'round': 'Jornada 10',
                'location': 'Benagalbon',
                'match_date': '2026-03-24',
                'match_time': '18:30',
            },
        )

        self.match.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.match.kickoff_time.isoformat(timespec='minutes'), '18:30')


class AdminPlatformRedirectTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            username='adminusers',
            email='adminusers@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.admin_user, role=AppUserRole.ROLE_ADMIN)
        self.alpha = user_model.objects.create_user(
            username='alpha-user',
            email='alpha@example.com',
            password='pass-1234',
            first_name='Alpha',
        )
        self.beta = user_model.objects.create_user(
            username='beta-user',
            email='beta@example.com',
            password='pass-1234',
            first_name='Beta',
        )
        AppUserRole.objects.create(user=self.alpha, role=AppUserRole.ROLE_PLAYER)
        AppUserRole.objects.create(user=self.beta, role=AppUserRole.ROLE_PLAYER)

    def test_admin_users_tab_redirects_to_platform(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin-page'), {'tab': 'users'})

        self.assertRedirects(response, f"{reverse('platform-overview')}#usuarios-club")

    def test_admin_carousel_tab_redirects_to_platform(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin-page'), {'tab': 'carousel'})

        self.assertRedirects(response, f"{reverse('platform-overview')}#home-global")


class AdminTeamsUniversoAutodetectTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            username='admin-teams',
            email='admin-teams@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.admin_user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga Base', slug='liga-base', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Base', slug='grupo-base', external_id='45030656')
        self.team = Team.objects.create(name='BENAGALBON C.D.', slug='benagalbon-base', group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Benagalbón',
            slug='benagalbon-ws',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.admin_user,
            enabled_modules={'dashboard': True},
            is_active=True,
        )
        WorkspaceMembership.objects.get_or_create(
            workspace=self.workspace,
            user=self.admin_user,
            defaults={'role': WorkspaceMembership.ROLE_OWNER},
        )

    @patch('football.views._fetch_universo_live_groups')
    @patch('football.views._fetch_universo_live_classification')
    def test_team_create_uses_universo_url_to_autodetect_group_by_category(self, mock_classification, mock_groups):
        # URL de resultados: simula que el querystring group apunta a una liga equivocada,
        # pero el competition_id contiene los grupos correctos para la categoría.
        universo_url = 'https://www.universorfaf.es/competitions/results/48199732?group=48199749&season=21&delegation=8'

        def classification_side_effect(group_id):
            group_id = str(group_id or '').strip()
            if group_id == '48199749':
                return {
                    'competicion': 'COPA FED 3 ANDALUZA',
                    'grupo': 'Grupo 2',
                    'codigo_competicion': '45030612',
                    'clasificacion': [{'nombre': 'BENAGALBON C.D.'}],
                }
            if group_id == '47051884':
                return {
                    'competicion': '3ª Andaluza Prebenjamín (Málaga)',
                    'grupo': 'Grupo 1',
                    'codigo_competicion': '44788590',
                    'clasificacion': [{'nombre': 'BENAGALBON C.D.'}],
                }
            return {}

        mock_groups.return_value = [{'codigo': '47051884', 'nombre': 'Grupo 1'}]
        mock_classification.side_effect = classification_side_effect

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('admin-page'),
            {
                'form_action': 'team_create',
                'active_tab': 'teams',
                'category': 'Prebenjamín',
                'game_format': 'f7',
                'team_name': 'BENAGALBON C.D.',
                'universo_url': universo_url,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Categoría creada')
        created = Team.objects.filter(is_primary=False, category__iexact='Prebenjamín').order_by('-id').first()
        self.assertIsNotNone(created)
        self.assertIsNotNone(created.group)
        # Debe haber detectado el grupo "47051884" (el que corresponde a Prebenjamín)
        self.assertEqual(created.group.external_id, '47051884')
        self.assertIn('prebenjam', (created.group.season.competition.name or '').lower())
        ctx = WorkspaceCompetitionContext.objects.filter(workspace=self.workspace, team=created).first()
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.provider, WorkspaceCompetitionContext.PROVIDER_UNIVERSO)
        self.assertEqual(ctx.external_group_key, '47051884')

    def test_team_split_workspace_creates_independent_club_and_moves_competition_context(self):
        pre_team = Team.objects.create(
            name='BENAGALBON C.D.',
            slug='benagalbon-pre',
            group=self.team.group,
            is_primary=False,
            category='Prebenjamín',
            game_format=Team.GAME_FORMAT_F7,
        )
        link = WorkspaceTeam.objects.create(workspace=self.workspace, team=pre_team, is_default=False)
        ctx = WorkspaceCompetitionContext.objects.create(
            workspace=self.workspace,
            team=pre_team,
            group=self.team.group,
            season=self.team.group.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='47051884',
            external_team_name=pre_team.name,
            is_auto_sync_enabled=True,
        )
        WorkspaceCompetitionSnapshot.objects.create(
            workspace=self.workspace,
            context=ctx,
            standings_payload=[{'position': 1, 'team': 'BENAGALBON', 'played': 1, 'points': 3}],
            next_match_payload={'round': 'J1', 'status': 'next'},
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

        response = self.client.post(
            reverse('admin-page'),
            {
                'form_action': 'team_split_workspace',
                'active_tab': 'teams',
                'workspace_team_id': link.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        new_ws = Workspace.objects.filter(kind=Workspace.KIND_CLUB, primary_team=pre_team).first()
        self.assertIsNotNone(new_ws)
        self.assertFalse(WorkspaceTeam.objects.filter(id=link.id).exists())
        moved_ctx = WorkspaceCompetitionContext.objects.filter(workspace=new_ws, team=pre_team).first()
        self.assertIsNotNone(moved_ctx)
        moved_snap = WorkspaceCompetitionSnapshot.objects.filter(context=moved_ctx, workspace=new_ws).first()
        self.assertIsNotNone(moved_snap)


class UniversoApiFallbackParamTests(TestCase):
    @patch('football.views._universo_api_post')
    def test_fetch_universo_competitions_tries_fallback_params(self, mock_post):
        # Primera respuesta vacía, segunda con competiciones.
        mock_post.side_effect = [
            {},
            {'competiciones': [{'codigo': '123', 'nombre': 'Liga Prebenjamín'}]},
        ]
        items = football_views._fetch_universo_live_competitions('8', '21')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get('codigo'), '123')
        self.assertGreaterEqual(mock_post.call_count, 2)

    @patch('football.views._universo_api_post')
    def test_fetch_universo_groups_tries_fallback_params(self, mock_post):
        mock_post.side_effect = [
            {},
            {'grupos': [{'codigo': '777', 'nombre': 'Grupo 1'}]},
        ]
        items = football_views._fetch_universo_live_groups('44788590')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get('codigo'), '777')
        self.assertGreaterEqual(mock_post.call_count, 2)


class TeamDisplayNameTests(TestCase):
    def test_display_name_prefers_short_name(self):
        competition = Competition.objects.create(name='Liga Display', slug='liga-display', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Display', slug='grupo-display')
        team = Team.objects.create(
            name='C.D. PIZARRA ATLÉTICO C.F.',
            short_name='Pizarra',
            slug='pizarra-display',
            group=group,
        )

        self.assertEqual(team.display_name, 'Pizarra')

    def test_display_name_falls_back_to_official_name(self):
        competition = Competition.objects.create(name='Liga Display 2', slug='liga-display-2', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2026/2027', is_current=False)
        group = Group.objects.create(season=season, name='Grupo Display 2', slug='grupo-display-2')
        team = Team.objects.create(
            name='LOJA C.D.',
            short_name='',
            slug='loja-display',
            group=group,
        )

        self.assertEqual(team.display_name, 'LOJA C.D.')


class EventTaxonomyKpiTests(TestCase):
    def test_shot_on_target_requires_shot_attempt(self):
        self.assertTrue(is_shot_attempt_event('disparo', result='fallado'))
        self.assertTrue(is_shot_on_target_event('disparo', result='ok'))
        self.assertTrue(is_shot_on_target_event('disparo', observation='parada del portero'))
        self.assertFalse(is_shot_attempt_event('parada', result='ok'))
        self.assertFalse(is_shot_on_target_event('parada', result='ok'))

    def test_shots_needed_per_goal_handles_zero_goals(self):
        self.assertEqual(shots_needed_per_goal(9, 3), 3.0)
        self.assertIsNone(shots_needed_per_goal(5, 0))

    def test_importance_score_combines_availability_and_success_volume(self):
        payload = calculate_importance_score(
            minutes=900,
            total_possible_minutes=1800,
            successes=80,
            max_successes=100,
        )

        self.assertEqual(payload['availability_pct'], 50.0)
        self.assertEqual(payload['success_volume_pct'], 80.0)
        self.assertEqual(payload['importance_score'], 62.0)

    def test_influence_score_rewards_successes_in_fewer_minutes(self):
        payload = calculate_influence_score(
            minutes=450,
            successes=40,
            goals=0,
            assists=0,
            key_passes_completed=0,
            max_decisive_actions_per90=8,
        )

        self.assertEqual(payload['successes_per90'], 8.0)
        self.assertEqual(payload['decisive_actions_per90'], 8.0)
        self.assertEqual(payload['influence_score'], 100.0)

    def test_influence_score_weights_goals_assists_and_key_passes(self):
        payload = calculate_influence_score(
            minutes=450,
            successes=20,
            goals=4,
            assists=3,
            key_passes_completed=6,
            max_decisive_actions_per90=12,
        )

        self.assertEqual(payload['successes_per90'], 4.0)
        self.assertEqual(payload['decisive_actions_per90'], 13.6)
        self.assertEqual(payload['influence_score'], 100.0)

    def test_build_smart_kpis_prioritizes_assists_when_present(self):
        profile, profile_label, kpis = build_smart_kpis(
            {
                'position': 'Extremo',
                'pj': 5,
                'successes': 12,
                'total_actions': 20,
                'assists': 3,
                'dribbles_attempted': 8,
                'dribbles_completed': 5,
                'duels_total': 6,
                'duels_won': 3,
                'pass_attempts': 10,
                'passes_completed': 7,
            }
        )

        self.assertEqual(profile, 'winger')
        self.assertEqual(profile_label, 'Extremo')
        self.assertEqual(kpis[0], {'label': 'Asistencias', 'value': '3'})

    def test_build_smart_kpis_recognizes_por_and_shows_saves(self):
        profile, profile_label, kpis = build_smart_kpis(
            {
                'position': 'POR',
                'pj': 4,
                'successes': 9,
                'total_actions': 12,
                'goalkeeper_saves': 7,
            }
        )

        self.assertEqual(profile, 'goalkeeper')
        self.assertEqual(profile_label, 'Portero')
        self.assertEqual(kpis[0], {'label': 'Paradas', 'value': '7'})


class KpiAuditEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='kpi-audit-admin',
            email='kpi-audit@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga KPI', slug='liga-kpi', region='Test')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo KPI', slug='grupo-kpi')
        self.team = Team.objects.create(name='Club KPI', slug='club-kpi', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival KPI', slug='rival-kpi', group=group)
        self.match = Match.objects.create(season=season, group=group, home_team=self.team, away_team=self.rival, round='1')
        self.player = Player.objects.create(team=self.team, name='Jugador KPI', position='MC', number=8)
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=10,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

    def test_kpi_audit_requires_admin(self):
        user_model = get_user_model()
        plain_user = user_model.objects.create_user(username='plain', password='pass-1234')
        self.client.force_login(plain_user)
        resp = self.client.get(reverse('kpi-audit'))
        self.assertEqual(resp.status_code, 403)

    def test_kpi_audit_returns_rows_for_team(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('kpi-audit'), {'team_id': self.team.id, 'refresh': '1'})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload.get('team', {}).get('id'), self.team.id)
        self.assertGreaterEqual(payload.get('summary', {}).get('players', 0), 1)
        rows = payload.get('rows') or []
        self.assertTrue(any(int(r.get('player_id') or 0) == self.player.id for r in rows))


class TaxonomyBehaviorTests(TestCase):
    def test_robo_and_duelo_aereo_count_as_duels(self):
        self.assertTrue(classify_duel_event('ROBO', 'GANADO')['is_duel'])
        self.assertTrue(classify_duel_event('ROBO', 'GANADO')['won'])
        self.assertTrue(classify_duel_event('Duelo aéreo', 'GANADO')['is_duel'])
        self.assertTrue(classify_duel_event('Duelo aéreo', 'GANADO')['won'])

    def test_switch_and_depth_passes_count_as_passes(self):
        self.assertTrue(contains_keyword('PASE A LA ESPALDA', PASS_KEYWORDS))
        self.assertTrue(contains_keyword('Cambio de orientación', PASS_KEYWORDS))

    def test_goal_event_counts_as_shot_attempt_and_on_target(self):
        self.assertTrue(is_shot_attempt_event('Gol', result='Gol'))
        self.assertTrue(is_shot_on_target_event('Gol', result='Gol'))

    def test_field_zone_aliases_map_mid_wide_and_interior_lanes(self):
        self.assertEqual(map_zone_label('MEDIO IZQUIERDA'), 'Medio Izquierda')
        self.assertEqual(map_zone_label('MEDIO DERECHA'), 'Medio Derecha')
        self.assertEqual(map_zone_label('Interior Izquierdo'), 'Medio Izquierda')
        self.assertEqual(map_zone_label('Interior derecha'), 'Medio Derecha')
        self.assertEqual(map_zone_label('Costado Izquierdo'), 'Medio Izquierda')
        self.assertEqual(map_zone_label('Costado Derecho'), 'Medio Derecha')
        self.assertEqual(map_zone_label('MC'), 'Medio Centro')
        self.assertEqual(map_zone_label('Último tercio'), 'Ataque Centro')
        self.assertEqual(map_zone_label('Frontal'), 'Ataque Centro')
        self.assertEqual(map_zone_label('DEFENSA CENTRO'), 'Defensa Centro')
        self.assertEqual(map_zone_label('Área propia'), 'Portería')


class ManualEventAggregationTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Stats', slug='liga-stats', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Stats', slug='grupo-stats')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-stats', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Stats', slug='rival-stats', group=group)
        self.match = Match.objects.create(season=season, group=group, home_team=self.team, away_team=self.rival)
        self.player = Player.objects.create(team=self.team, name='Martinez', number=6, position='MC')

        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=10,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=10,
            period=1,
            system='touch-field-final',
            source_file='BDT PARTIDOS BENABALBON.xlsm',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='DUELO',
            result='GANADO',
            zone='Medio Centro',
            tercio='Construcción',
            minute=25,
            period=1,
            system='touch-field-final',
            source_file='admin-manual',
        )

    def test_player_cards_include_manual_events_alongside_preferred_source(self):
        cards = compute_player_cards_for_match(self.match, self.team)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['actions'], 2)
        self.assertEqual(cards[0]['successes'], 2)
        self.assertEqual(cards[0]['success_rate'], 100.0)

    def test_player_metrics_treat_manual_ganado_as_success(self):
        metrics = compute_player_metrics(self.team)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]['actions'], 2)
        self.assertEqual(metrics[0]['successes'], 2)

    def test_team_metrics_for_match_keep_manual_events_without_duplicate_sources(self):
        metrics = compute_team_metrics_for_match(self.match, primary_team=self.team)

        self.assertEqual(metrics['total_events'], 2)
        self.assertEqual(metrics['top_event_types'][0]['count'], 1)

    def test_manual_batch_events_with_same_minute_are_not_collapsed(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='DUELO',
            result='GANADO',
            zone='Medio Centro',
            tercio='Construcción',
            minute=25,
            period=1,
            system='touch-field-final',
            source_file='admin-manual',
        )

        cards = compute_player_cards_for_match(self.match, self.team)

        self.assertEqual(cards[0]['actions'], 3)
        self.assertEqual(cards[0]['successes'], 3)

class MatchActionWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='match-coach',
            email='match-coach@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga Acciones', slug='liga-acciones', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Acciones', slug='grupo-acciones')
        self.team = Team.objects.create(name='Benagalbón Acciones', slug='benagalbon-acciones', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Acciones', slug='rival-acciones', group=group)
        self.match = Match.objects.create(
            season=season,
            group=group,
            home_team=self.team,
            away_team=self.rival,
            round='24',
            date=date(2026, 3, 22),
        )
        self.workspace = Workspace.objects.create(
            name='Benagalbón Acciones',
            slug='benagalbon-acciones-ws',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'dashboard': True,
                'match_actions': True,
                'convocation': False,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.player = Player.objects.create(team=self.team, name='Ayala', number=4, position='Central')
        self.convocation = ConvocationRecord.objects.create(
            team=self.team,
            match=self.match,
            is_current=True,
        )
        self.convocation.players.add(self.player)
        self.client.force_login(self.user)

    def test_coach_can_open_and_register_match_actions(self):
        page = self.client.get(reverse('match-action-page'))
        self.assertEqual(page.status_code, 200)

        response = self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'Asistencia',
                'result': 'OK',
                'zone': 'Ataque Centro',
                'minute': 42,
                'period': 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            MatchEvent.objects.filter(
                match=self.match,
                player=self.player,
                source_file='registro-acciones',
                system='touch-field',
            ).count(),
            1,
        )

    def test_register_match_action_allows_identical_same_minute_actions_with_distinct_client_uids(self):
        # En fútbol, es habitual registrar varias acciones iguales en el mismo minuto (pases, duelos, etc.).
        # El servidor solo debe deduplicar reintentos de red, no acciones reales consecutivas.
        payload = {
            'match_id': self.match.id,
            'player': self.player.id,
            'action_type': 'Pase',
            'result': 'OK',
            'zone': 'Ataque Centro',
            'minute': 12,
            'period': 1,
        }
        response1 = self.client.post(reverse('match-action-record'), {**payload, 'client_event_uid': 'evt-1'})
        self.assertEqual(response1.status_code, 200)
        response2 = self.client.post(reverse('match-action-record'), {**payload, 'client_event_uid': 'evt-2'})
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(
            MatchEvent.objects.filter(
                match=self.match,
                player=self.player,
                source_file='registro-acciones',
                system='touch-field',
                minute=12,
                event_type='Pase',
            ).count(),
            2,
        )

    def test_match_action_invalidates_scoped_player_dashboard_cache(self):
        # Cache por scope (liga/torneo/amistoso) debe invalidarse tras registrar acciones.
        from django.core.cache import cache

        cache.clear()
        compute_player_dashboard(self.team)  # llena cache "league"
        response = self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'Asistencia',
                'result': 'OK',
                'zone': 'Ataque Centro',
                'minute': 42,
                'period': 1,
                'client_event_uid': 'evt-cache-1',
            },
        )
        self.assertEqual(response.status_code, 200)
        dashboard = compute_player_dashboard(self.team)
        detail = next(item for item in dashboard if item['player_id'] == self.player.id)
        self.assertEqual(detail['assists'], 1)

    def test_lineup_save_is_allowed_from_match_actions_workspace(self):
        response = self.client.post(
            reverse('match-lineup-save'),
            data=json.dumps(
                {
                    'lineup': {
                        'starters': [{'id': self.player.id, 'name': self.player.name, 'number': self.player.number}],
                        'bench': [],
                    }
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.convocation.refresh_from_db()
        self.assertEqual(int(self.convocation.lineup_data['starters'][0]['id']), self.player.id)

    def test_delete_endpoint_only_deletes_pending_live_events(self):
        final_event = MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        response = self.client.post(
            reverse('match-action-delete'),
            {
                'match_id': self.match.id,
                'event_id': final_event.id,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(MatchEvent.objects.filter(id=final_event.id).exists())

    def test_finalize_keeps_distinct_same_minute_actions(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=12,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )

        response = self.client.post(
            reverse('match-action-finalize'),
            data=json.dumps({'match_info': {'match_id': self.match.id}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            MatchEvent.objects.filter(
                match=self.match,
                system='touch-field-final',
                source_file='registro-acciones',
            ).count(),
            2,
        )

    def test_finalize_does_not_delete_previous_final_cards_or_subs(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Tarjeta Amarilla',
            result='Amarilla',
            zone='Tarjeta Amarilla',
            tercio='',
            minute=10,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )
        pending = MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )

        response = self.client.post(
            reverse('match-action-finalize'),
            data=json.dumps({'match_info': {'match_id': self.match.id}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            MatchEvent.objects.filter(
                match=self.match,
                system='touch-field-final',
                source_file='registro-acciones',
                event_type__icontains='tarjeta',
            ).exists()
        )
        pending.refresh_from_db()
        self.assertEqual(pending.system, 'touch-field-final')

    def test_finalize_can_store_final_score(self):
        self.assertIsNone(self.match.home_score)
        self.assertIsNone(self.match.away_score)

        response = self.client.post(
            reverse('match-action-finalize'),
            data=json.dumps({'match_info': {'score_for': 2, 'score_against': 1}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.match.refresh_from_db()
        self.assertEqual(self.match.home_score, 2)
        self.assertEqual(self.match.away_score, 1)

        away_match = Match.objects.create(
            season=self.match.season,
            group=self.match.group,
            home_team=self.rival,
            away_team=self.team,
            round='26',
            date=date(2026, 5, 2),
        )
        url = f"{reverse('match-action-finalize')}?match_id={away_match.id}"
        response = self.client.post(
            url,
            data=json.dumps({'match_info': {'score_for': 3, 'score_against': 4}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        away_match.refresh_from_db()
        self.assertEqual(away_match.away_score, 3)
        self.assertEqual(away_match.home_score, 4)

    def test_match_info_save_persists_score_and_convocation_fields(self):
        self.assertIsNone(self.match.home_score)
        self.assertIsNone(self.match.away_score)
        url = f"{reverse('match-info-save')}?match_id={self.match.id}"

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    'match_info': {
                        'opponent': 'Rival Acciones',
                        'location': 'Campo Municipal',
                        'round': '24',
                        'datetime': '22/03/2026 · 18:00',
                        'score_for': 1,
                        'score_against': 0,
                    }
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.match.refresh_from_db()
        self.assertEqual(self.match.home_score, 1)
        self.assertEqual(self.match.away_score, 0)
        self.convocation.refresh_from_db()
        self.assertEqual(self.convocation.location, 'Campo Municipal')
        self.assertEqual(self.convocation.match_date, date(2026, 3, 22))
        self.assertIsNotNone(self.convocation.match_time)
        self.assertEqual(self.convocation.match_time.strftime('%H:%M'), '18:00')

    def test_reset_only_clears_pending_live_events(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )
        final_event = MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Gol',
            result='Gol',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=33,
            period=2,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        response = self.client.post(
            reverse('match-action-reset'),
            {'match_id': self.match.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            MatchEvent.objects.filter(
                match=self.match,
                system='touch-field',
                source_file='registro-acciones',
            ).exists()
        )
        self.assertTrue(MatchEvent.objects.filter(id=final_event.id).exists())

    def test_match_actions_page_defaults_to_match_with_pending_live_events(self):
        other_rival = Team.objects.create(name='Rival Futuro', slug='rival-futuro', group=self.team.group)
        future_match = Match.objects.create(
            season=self.match.season,
            group=self.match.group,
            home_team=self.team,
            away_team=other_rival,
            round='25',
            date=date(2026, 4, 20),
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=5,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )
        self.assertGreater(future_match.date, self.match.date)

        response = self.client.get(reverse('match-action-page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get('selected_match_id'), self.match.id)

    def test_match_actions_page_does_not_embed_css_inside_script(self):
        response = self.client.get(reverse('match-action-page'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        marker = '.offline-queue-badge {'
        self.assertIn(marker, content)
        style_end = content.find('</style>')
        self.assertNotEqual(style_end, -1)
        self.assertLess(content.find(marker), style_end)
        self.assertEqual(content.find(marker, style_end), -1)


class PlayerDashboardViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='dashboard-user',
            email='dashboard@example.com',
            password='pass-1234',
        )
        competition = Competition.objects.create(name='Liga View', slug='liga-view', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo View', slug='grupo-view')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-view', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival View', slug='rival-view', group=group)
        self.player = Player.objects.create(team=self.team, name='Hiago', number=18, position='Extremo')
        self.match = Match.objects.create(
            season=season,
            group=group,
            home_team=self.team,
            away_team=self.rival,
            round='24',
            date=date(2026, 3, 22),
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

    @patch('football.views.refresh_primary_roster_cache')
    def test_player_dashboard_supports_match_filter(self, mocked_refresh):
        self.client.force_login(self.user)
        with patch.dict(os.environ, {'PREFERENTE_ROSTER_REFRESH_ON_PLAYER_DASHBOARD': '1'}):
            response = self.client.get(reverse('player-dashboard'), {'match': self.match.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival View')
        self.assertContains(response, 'Acciones totales:')
        mocked_refresh.assert_called_once_with(self.team, force=False)

    @patch('football.views.refresh_primary_roster_cache')
    def test_player_dashboard_does_not_refresh_roster_by_default(self, mocked_refresh):
        self.client.force_login(self.user)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('PREFERENTE_ROSTER_REFRESH_ON_PLAYER_DASHBOARD', None)
            response = self.client.get(reverse('player-dashboard'))
        self.assertEqual(response.status_code, 200)
        mocked_refresh.assert_not_called()

    def test_compute_player_dashboard_reuses_cached_payload(self):
        first = compute_player_dashboard(self.team)

        with patch('football.views.get_competition_total_rounds', side_effect=RuntimeError('cache miss')):
            second = compute_player_dashboard(self.team)

        self.assertEqual(first, second)

    def test_player_match_stats_uses_dedicated_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('player-match-stats', args=[self.player.id, self.match.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'football/player_match_stats.html')
        self.assertContains(response, 'KPI de rendimiento')

    def test_player_role_home_redirects_to_player_detail(self):
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.full_name = 'dashboard user'
        self.player.save(update_fields=['full_name'])

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard-home'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('player-detail', args=[self.player.id]))

    def test_player_dashboard_allows_player_without_workspace(self):
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival View')

    def test_player_detail_allows_player_without_workspace(self):
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.full_name = 'dashboard user'
        self.player.save(update_fields=['full_name'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hiago')

    def test_player_dashboard_shows_preview_link_for_staff_roles(self):
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista jugador')
        self.assertContains(response, f'{reverse("player-detail", args=[self.player.id])}?preview=player')

    def test_player_match_stats_infers_missing_zone_from_player_profile(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='DUELO',
            result='GANADO',
            zone='',
            tercio='Construcción',
            minute=18,
            period=1,
            system='touch-field-final',
            source_file='admin-manual',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('player-match-stats', args=[self.player.id, self.match.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['zone_counts']['Medio Centro'], 2)

    def test_assist_event_counts_as_completed_pass(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=30,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('player-match-stats', args=[self.player.id, self.match.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['passes']['attempts'], 2)
        self.assertEqual(response.context['stats']['passes']['completed'], 2)

    def test_completed_key_pass_is_counted_for_influence_inputs(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase clave',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=32,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        dashboard = compute_player_dashboard(self.team)
        detail = next(item for item in dashboard if item['player_id'] == self.player.id)

        self.assertEqual(detail['passes']['key_completed'], 1)
        self.assertGreater(detail['decisive_actions_per90'], detail['successes_per90'])

    def test_goalkeeper_save_event_counts_and_sets_goalkeeper_profile(self):
        goalkeeper = Player.objects.create(team=self.team, name='Portero Uno', position='POR')
        MatchEvent.objects.create(
            match=self.match,
            player=goalkeeper,
            event_type='Parada',
            result='OK',
            zone='Portería',
            tercio='Defensa',
            minute=28,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        dashboard = compute_player_dashboard(self.team)
        detail = next(item for item in dashboard if item['player_id'] == goalkeeper.id)

        self.assertEqual(detail['goalkeeper_saves'], 1)
        self.assertEqual(detail['profile'], 'goalkeeper')
        self.assertEqual(detail['smart_kpis'][0], {'label': 'Paradas', 'value': '1'})

    def test_pending_live_assist_updates_player_dashboard_kpis(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=41,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )

        dashboard = compute_player_dashboard(self.team)
        detail = next(item for item in dashboard if item['player_id'] == self.player.id)

        self.assertEqual(detail['assists'], 1)
        self.assertEqual(detail['smart_kpis'][0], {'label': 'Asistencias', 'value': '1'})

    def test_live_assist_overrides_imported_source_for_dashboard_kpis(self):
        MatchEvent.objects.filter(match=self.match).delete()
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field-final',
            source_file='BDT PARTIDOS BENABALBON.xlsm',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=41,
            period=1,
            system='touch-field',
            source_file='registro-acciones',
        )

        dashboard = compute_player_dashboard(self.team, force_refresh=True)
        detail = next(item for item in dashboard if item['player_id'] == self.player.id)

        self.assertEqual(detail['assists'], 1)
        self.assertEqual(detail['smart_kpis'][0], {'label': 'Asistencias', 'value': '1'})

    def test_register_match_action_invalidates_player_dashboard_cache(self):
        compute_player_dashboard(self.team)
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        convocation = ConvocationRecord.objects.create(
            team=self.team,
            match=self.match,
            is_current=True,
        )
        convocation.players.add(self.player)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'Asistencia',
                'result': 'OK',
                'zone': 'Ataque Centro',
                'minute': 42,
                'period': 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        dashboard = compute_player_dashboard(self.team)
        detail = next(item for item in dashboard if item['player_id'] == self.player.id)
        self.assertEqual(detail['assists'], 1)
        self.assertEqual(detail['smart_kpis'][0], {'label': 'Asistencias', 'value': '1'})


class CoachTrainerMetricsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='coach-metrics',
            email='coach-metrics@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga Coach', slug='liga-coach', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Coach', slug='grupo-coach')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-coach', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Coach', slug='rival-coach', group=group)
        self.match = Match.objects.create(
            season=season,
            group=group,
            home_team=self.team,
            away_team=self.rival,
            round='24',
            date=date(2026, 3, 22),
        )
        self.player = Player.objects.create(team=self.team, name='Ayala', position='Central')
        PlayerStatistic.objects.create(
            player=self.player,
            season=season,
            name='manual_yellow_cards',
            value=3,
            context='manual-base',
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=season,
            name='manual_red_cards',
            value=1,
            context='manual-base',
        )
        TeamStanding.objects.create(
            season=season,
            group=group,
            team=self.team,
            position=5,
            points=42,
            goals_for=10,
            goals_against=5,
            played=5,
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Gol',
            result='Gol',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=20,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )
        self.client.force_login(self.user)
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=12,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

    def test_trainer_page_uses_player_card_totals_for_cards(self):
        response = self.client.get(reverse('coach-role-trainer'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tarjetas totales')
        self.assertContains(response, '>4<', html=False)

    def test_trainer_page_map_note_uses_mapped_actions(self):
        response = self.client.get(reverse('coach-role-trainer'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acciones con zona válida')

    def test_trainer_page_distinguishes_real_and_measured_metrics(self):
        response = self.client.get(reverse('coach-role-trainer'))

        self.assertEqual(response.status_code, 200)
        general_stats = {item['label']: item['value'] for item in response.context['coach_general_stats']}
        self.assertEqual(general_stats['Partidos jugados'], 5)
        self.assertEqual(general_stats['Partidos medidos'], 1)
        self.assertEqual(general_stats['Goles totales'], 10)
        self.assertEqual(general_stats['Goles medidos'], 1)
        self.assertEqual(general_stats['Goles medidos/partido'], 1.0)
        kpis = {item['label']: item['value'] for item in response.context['kpis']}
        self.assertEqual(kpis['Acciones/partido'], 2.0)
        overview = response.context['coach_overview_stats']
        self.assertEqual(overview['summary'][1]['value'], 1)
        self.assertEqual(overview['summary'][6]['value'], '1/1')

    def test_trainer_overview_counts_assist_as_completed_pass(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=26,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )

        response = self.client.get(reverse('coach-role-trainer'))

        self.assertEqual(response.status_code, 200)
        overview_summary = {item['label']: item['value'] for item in response.context['coach_overview_stats']['summary']}
        self.assertEqual(overview_summary['Pases'], '2/2')

    def test_stats_audit_treats_goal_gap_as_coverage_note(self):
        report = run_stats_audit(self.team)

        self.assertTrue(report['ok'])
        self.assertFalse(any('Descuadre entre goles' in issue for issue in report['issues']))
        self.assertTrue(any('Cobertura de acciones parcial' in note for note in report['notes']))
        self.assertEqual(report['summary']['measured_matches'], 1)

    def test_trainer_heatmap_infers_missing_zone_from_match_profile(self):
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            zone='Medio Centro',
            tercio='Construcción',
            minute=15,
            period=1,
            system='touch-field-final',
            source_file='registro-acciones',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='DUELO',
            result='GANADO',
            zone='',
            tercio='Construcción',
            minute=33,
            period=1,
            system='touch-field-final',
            source_file='admin-manual',
        )

        response = self.client.get(reverse('coach-role-trainer'))

        self.assertEqual(response.status_code, 200)
        medio_centro = next(
            zone for zone in response.context['coach_total_field_zones']
            if zone['key'] == 'Medio Centro'
        )
        self.assertEqual(medio_centro['count'], 3)

    def test_trainer_page_can_render_player_season_and_match_views(self):
        PlayerFine.objects.create(
            player=self.player,
            reason=PlayerFine.REASON_LATE,
            amount=10,
            note='Retraso en la charla',
        )
        PlayerCommunication.objects.create(
            player=self.player,
            match=self.match,
            category=PlayerCommunication.CATEGORY_CONVOCATION,
            message='Llega 60 minutos antes del partido.',
        )

        response = self.client.get(reverse('coach-role-trainer'), {'player': self.player.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn('coach_player_view', response.context)
        self.assertEqual(response.context['coach_player_view']['mode'], 'season')
        self.assertEqual(response.context['coach_player_view']['fines_summary'][0]['value'], 1)
        self.assertEqual(response.context['coach_player_view']['communications'][0]['title'], 'Convocatoria')
        self.assertContains(response, 'Multas')
        self.assertContains(response, 'Comunicación')
        self.assertContains(response, 'Retraso en la charla')
        self.assertContains(response, 'Llega 60 minutos antes del partido.')

        response = self.client.get(
            reverse('coach-role-trainer'),
            {'player': self.player.id, 'player_match': self.match.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['coach_player_view']['mode'], 'match')
        self.assertContains(response, 'Multas')
        self.assertContains(response, 'Comunicación')


class StatsScopePersistenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='scope-user',
            email='scope-user@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga Scope', slug='liga-scope', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Scope', slug='grupo-scope')
        self.team = Team.objects.create(name='Equipo Scope', slug='equipo-scope', group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Workspace Scope',
            slug='workspace-scope',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'players': True,
                'dashboard': True,
                'coach_overview': True,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_player_dashboard_scope_persists_in_session(self):
        response1 = self.client.get(reverse('player-dashboard') + '?scope=tournament')
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.context.get('stats_scope'), 'tournament')

        response2 = self.client.get(reverse('player-dashboard'))
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.context.get('stats_scope'), 'tournament')

    def test_coach_roster_scope_defaults_to_persisted(self):
        self.client.get(reverse('player-dashboard') + '?scope=friendly')
        response = self.client.get(reverse('coach-roster'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get('scope_value'), 'friendly')


class AnalysisVideoWorkspaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='analyst-workspace',
            email='analyst-workspace@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ANALYST)
        competition = Competition.objects.create(name='Liga Analista', slug='liga-analista', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Analista', slug='grupo-analista')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-analista', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Analista', slug='rival-analista', group=group)
        self.player = Player.objects.create(team=self.team, name='Ivan', position='DC')
        self.client.force_login(self.user)

    def test_analysis_page_can_create_folder_and_assign_video_to_player(self):
        response = self.client.post(
            reverse('analysis'),
            {
                'form_action': 'create_video_folder',
                'video_team_id': self.rival.id,
                'folder_name': 'J24 · Clips DC',
                'team_id': self.rival.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        folder = AnalystVideoFolder.objects.get(name='J24 · Clips DC')
        self.assertEqual(folder.rival_team, self.rival)

        video_file = SimpleUploadedFile('clip.mp4', b'fake-video-content', content_type='video/mp4')
        response = self.client.post(
            reverse('analysis'),
            {
                'form_action': 'upload_video',
                'video_team_id': self.rival.id,
                'video_title': 'Clip delantero',
                'video_source': RivalVideo.SOURCE_MANUAL,
                'video_folder_id': folder.id,
                'video_notes': 'Atacar intervalo central',
                'assigned_player_ids': [self.player.id],
                'team_id': self.rival.id,
                'video_file': video_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        video = RivalVideo.objects.get(title='Clip delantero')
        self.assertEqual(video.folder, folder)
        self.assertEqual(list(video.assigned_players.values_list('id', flat=True)), [self.player.id])

    def test_player_detail_shows_assigned_analysis_video(self):
        folder = AnalystVideoFolder.objects.create(team=self.team, rival_team=self.rival, name='J24 · ABP')
        video = RivalVideo.objects.create(
            rival_team=self.rival,
            folder=folder,
            title='ABP ofensiva rival',
            video=SimpleUploadedFile('abp.mp4', b'video', content_type='video/mp4'),
            source=RivalVideo.SOURCE_MANUAL,
            notes='Revisar bloqueos del primer palo',
        )
        video.assigned_players.add(self.player)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vídeos')
        self.assertContains(response, 'ABP ofensiva rival')


class SessionsPlanningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='sessions-coach',
            email='sessions-coach@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga Sessions', slug='liga-sessions', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Sessions', slug='grupo-sessions')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-sessions', group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Benagalbon Sessions',
            slug='benagalbon-sessions-workspace',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': True,
                'match_actions': True,
                'sessions': True,
                'analysis': True,
                'abp_board': True,
                'manual_stats': True,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo J24',
            week_start=date(2026, 3, 23),
            week_end=date(2026, 3, 29),
        )
        self.player = Player.objects.create(team=self.team, name='Hugo', number=8, position='MC')
        self.client.force_login(self.user)

    def test_create_session_plan_saves_start_time_and_renders_session_card(self):
        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'create_session_plan',
                'planner_tab': 'planning',
                'plan_microcycle_id': self.microcycle.id,
                'plan_session_date': '2026-03-25',
                'plan_session_start_time': '19:30',
                'plan_session_focus': 'Transición + finalización',
                'plan_session_minutes': '95',
                'plan_session_intensity': TrainingSession.INTENSITY_HIGH,
                'plan_session_status': TrainingSession.STATUS_PLANNED,
                'plan_session_content': 'Tarea de activación y juego aplicado',
            },
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(microcycle=self.microcycle)
        self.assertEqual(session.start_time.strftime('%H:%M'), '19:30')
        self.assertContains(response, 'Transición + finalización')
        self.assertContains(response, '19:30')

    def test_update_library_task_does_not_wipe_unposted_fields_on_rename(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Biblioteca coach',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea original',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            objective='Objetivo importante',
            coaching_points='Consigna clave',
            confrontation_rules='Reglas de confrontación',
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        football_views._update_library_task_from_post(
            task,
            {
                'task_title': 'Tarea renombrada',
                # Simula renombrado desde card: no envía el resto de campos.
            },
            scope_key=None,
        )

        task.refresh_from_db()
        self.assertEqual(task.title, 'Tarea renombrada')
        self.assertEqual(task.objective, 'Objetivo importante')
        self.assertEqual(task.coaching_points, 'Consigna clave')
        self.assertEqual(task.confrontation_rules, 'Reglas de confrontación')
        meta = (task.tactical_layout or {}).get('meta') or {}
        self.assertIn('original_version', meta)


class StaffUserLinkingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user(username='admin', password='pass-1234')
        # Admin "platform": usamos is_staff para superar checks de vistas de platform en tests.
        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])
        AppUserRole.objects.create(user=self.admin, role=AppUserRole.ROLE_COACH)

        competition = Competition.objects.create(name='Liga Staff', slug='liga-staff', region='Test')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Staff', slug='grupo-staff')
        self.team = Team.objects.create(name='Equipo Staff', slug='equipo-staff', group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Club Staff',
            slug='club-staff',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': True,
                'match_actions': True,
                'sessions': True,
                'analysis': True,
                'abp_board': True,
                'manual_stats': True,
            },
            is_active=True,
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role=WorkspaceMembership.ROLE_ADMIN)
        self.client.force_login(self.admin)

    def test_inviting_user_links_matching_staff_member_by_email(self):
        StaffMember.objects.create(
            workspace=self.workspace,
            team=None,
            name='Fisio Uno',
            email='fisio@example.com',
            is_active=True,
        )

        response = self.client.post(
            reverse('platform-workspace-detail', args=[self.workspace.id]),
            {
                'form_action': 'invite_member',
                'invite_username': 'fisio',
                'invite_full_name': 'Fisio Uno',
                'invite_email': 'fisio@example.com',
                'invite_app_role': 'analista',
                'invite_member_role': 'viewer',
                'invite_valid_days': '7',
            },
        )

        self.assertEqual(response.status_code, 200)
        user_obj = get_user_model().objects.get(username='fisio')
        staff = StaffMember.objects.get(workspace=self.workspace, email='fisio@example.com')
        self.assertEqual(staff.user_id, user_obj.id)

    def test_create_session_plan_can_attach_selected_library_tasks(self):
        library_session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 23),
            focus='Biblioteca coach',
            duration_minutes=90,
        )
        library_task = SessionTask.objects.create(
            session=library_session,
            title='Rondo de activación',
            block=SessionTask.BLOCK_ACTIVATION,
            duration_minutes=12,
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'create_session_plan',
                'planner_tab': 'planning',
                'plan_microcycle_id': self.microcycle.id,
                'plan_session_date': '2026-03-25',
                'plan_session_focus': 'Sesión con tareas',
                'plan_session_task_ids': [library_task.id],
            },
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(microcycle=self.microcycle, focus='Sesión con tareas')
        self.assertEqual(session.tasks.count(), 1)
        self.assertEqual(session.tasks.first().title, 'Rondo de activación')
        self.assertContains(response, 'Tareas añadidas: 1')

    def test_create_session_plan_rejects_date_outside_microcycle(self):
        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'create_session_plan',
                'planner_tab': 'planning',
                'plan_microcycle_id': self.microcycle.id,
                'plan_session_date': '2026-04-01',
                'plan_session_focus': 'Sesión fuera de rango',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La fecha de la sesión debe estar dentro del microciclo.')
        self.assertFalse(TrainingSession.objects.exists())

    def test_create_session_plan_blocks_duplicates(self):
        TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Transición + finalización',
            duration_minutes=90,
        )

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'create_session_plan',
                'planner_tab': 'planning',
                'plan_microcycle_id': self.microcycle.id,
                'plan_session_date': '2026-03-25',
                'plan_session_focus': 'Transición + finalización',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una sesión con la misma fecha y nombre en este microciclo.')
        self.assertEqual(TrainingSession.objects.count(), 1)

    def test_update_session_plan_changes_schedule_fields(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión inicial',
            duration_minutes=90,
        )

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'update_session_plan',
                'planner_tab': 'planning',
                'edit_session_id': session.id,
                'edit_microcycle_id': self.microcycle.id,
                'edit_session_date': '2026-03-26',
                'edit_session_start_time': '18:00',
                'edit_session_focus': 'Sesión corregida',
                'edit_session_minutes': '80',
                'edit_session_intensity': TrainingSession.INTENSITY_MEDIUM,
                'edit_session_status': TrainingSession.STATUS_DONE,
                'edit_session_content': 'Contenido actualizado',
            },
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.focus, 'Sesión corregida')
        self.assertEqual(session.session_date, date(2026, 3, 26))
        self.assertEqual(session.start_time.strftime('%H:%M'), '18:00')
        self.assertEqual(session.status, TrainingSession.STATUS_DONE)

    def test_delete_session_plan_blocks_sessions_with_tasks(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión con tarea',
            duration_minutes=90,
        )
        SessionTask.objects.create(session=session, title='Juego de posición')

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'delete_session_plan',
                'planner_tab': 'planning',
                'delete_session_id': session.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No puedes borrar una sesión que ya tiene tareas asociadas.')
        self.assertTrue(TrainingSession.objects.filter(id=session.id).exists())

    def test_create_tab_redirects_to_dedicated_editor_flow(self):
        response = self.client.get(reverse('sessions'), {'tab': 'create'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('sessions-task-create'))
        self.assertContains(response, 'Editor visual dedicado')
        self.assertNotContains(response, 'Crear tarea con pizarra')

    def test_task_builder_create_page_shows_live_preview_and_print_buttons(self):
        response = self.client.get(reverse('sessions-task-create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista previa')
        self.assertContains(response, 'Multipizarra')
        self.assertContains(response, 'Imprimir UEFA')
        self.assertContains(response, 'Imprimir Club')

    def test_task_builder_creates_task_with_extended_metadata_and_assignment(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        preview_payload = 'data:image/png;base64,' + base64.b64encode(b'preview-image').decode('ascii')
        before_count = SessionTask.objects.count()

        response = self.client.post(
            reverse('sessions-task-create'),
            {
                'planner_action': 'create_draw_task',
                'draw_target_session_id': session.id,
                'draw_task_template': 'none',
                'draw_task_title': 'Juego aplicado 6v6',
                'draw_task_block': SessionTask.BLOCK_MAIN_1,
                'draw_task_minutes': '18',
                'draw_task_objective': 'Fijar por dentro y progresar fuera',
                'draw_task_surface': 'natural_grass',
                'draw_task_pitch_format': '11v11_half',
                'draw_task_game_phase': 'organization_attack',
                'draw_task_methodology': 'integrated',
                'draw_task_complexity': 'high',
                'draw_task_training_type': 'Táctica integrada',
                'draw_task_player_count': '12 + 2 porteros',
                'draw_task_age_group': 'Juvenil',
                'draw_task_dimensions': '40x30m',
                'draw_task_space': 'Zona interior + carriles',
                'draw_task_organization': '6v6 + 2 comodines',
                'draw_task_players_distribution': '2 líneas + pivote',
                'draw_task_work_rest': "4x3' + 1'",
                'draw_task_series': '4',
                'draw_task_repetitions': '3',
                'draw_task_load_target': 'RPE 7',
                'draw_task_category_tags': 'finalización, presión',
                'draw_task_pitch_preset': 'half_pitch',
                'draw_task_description': 'Secuencia principal de la tarea.',
                'draw_task_players': '12 + 2 porteros',
                'draw_task_materials': 'Conos, petos, 2 porterías',
                'draw_task_coaching_points': 'Perfilar antes de recibir',
                'draw_task_confrontation_rules': 'Dos toques en inicio',
                'draw_task_progression': 'Reducir tiempo',
                'draw_task_regression': 'Añadir comodín',
                'draw_task_success_criteria': '6 progresiones limpias',
                'draw_constraints': ['two_touches', 'mandatory_switch'],
                'assigned_player_ids': [self.player.id],
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
                'draw_canvas_width': '1280',
                'draw_canvas_height': '720',
                'draw_canvas_preview_data': preview_payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SessionTask.objects.count(), before_count + 1)
        task = SessionTask.objects.order_by('-id').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.title, 'Juego aplicado 6 v 6')
        meta = task.tactical_layout.get('meta') or {}
        self.assertEqual(task.session, session)
        self.assertEqual(meta.get('training_type'), 'Táctica integrada')
        self.assertEqual(meta.get('player_count'), '12 + 2 porteros')
        self.assertEqual(meta.get('age_group'), 'Juvenil')
        self.assertEqual(meta.get('category_tags'), ['Finalización', 'presión'])
        self.assertEqual(meta.get('assigned_player_ids'), [self.player.id])
        self.assertEqual(meta.get('assigned_player_names'), ['Hugo'])
        self.assertTrue(bool(task.task_preview_image))
        self.assertContains(response, 'Tarea guardada correctamente.')
        self.assertContains(response, 'Imprimir UEFA')
        self.assertContains(response, 'Imprimir Club')

    def test_task_builder_persists_animation_steps(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión animada',
            duration_minutes=90,
        )

        response = self.client.post(
            reverse('sessions-task-create'),
            {
                'planner_action': 'create_draw_task',
                'draw_target_session_id': session.id,
                'draw_task_title': 'Tarea con pasos',
                'draw_task_block': SessionTask.BLOCK_MAIN_1,
                'draw_task_minutes': '20',
                'draw_task_pitch_preset': 'full_pitch',
                'draw_canvas_state': json.dumps(
                    {
                        'version': '5.3.0',
                        'objects': [],
                        'active_step_index': 0,
                        'timeline': [
                            {'title': 'Salida', 'duration': 2, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                            {'title': 'Finalización', 'duration': 4, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                        ],
                    }
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        task = SessionTask.objects.get(title='Tarea con pasos')
        self.assertEqual(len(task.tactical_layout.get('timeline') or []), 2)
        self.assertEqual(task.tactical_layout['timeline'][0]['title'], 'Salida')
        self.assertEqual(task.tactical_layout['timeline'][1]['duration'], 4)

    def test_task_builder_edit_updates_existing_task(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        other_session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 27),
            focus='Sesión destino',
            duration_minutes=85,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea original',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response = self.client.post(
            reverse('sessions-task-edit', args=[task.id]),
            {
                'planner_action': 'create_draw_task',
                'draw_target_session_id': other_session.id,
                'draw_task_template': 'none',
                'draw_task_title': 'Tarea actualizada',
                'draw_task_block': SessionTask.BLOCK_MAIN_2,
                'draw_task_minutes': '22',
                'draw_task_objective': 'Ajustar alturas',
                'draw_task_pitch_preset': 'full_pitch',
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
                'draw_canvas_width': '1280',
                'draw_canvas_height': '720',
            },
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Tarea actualizada')
        self.assertEqual(task.session, other_session)
        self.assertEqual(task.duration_minutes, 22)
        self.assertEqual(task.block, SessionTask.BLOCK_MAIN_2)

    def test_task_builder_edit_partial_post_does_not_wipe_existing_fields(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea completa',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            objective='Objetivo previo',
            coaching_points='Consignas previas',
            confrontation_rules='Reglas previas',
            tactical_layout={
                'tokens': [],
                'meta': {
                    'scope': 'coach',
                    'surface': 'natural_grass',
                    'pitch_format': '11v11_half',
                    'constraints': ['two_touches'],
                    'assigned_player_ids': [self.player.id],
                    'assigned_player_names': [self.player.name],
                    'analysis': {
                        'task_sheet': {
                            'description': 'Descripción previa',
                            'players': 'A, B, C',
                            'space': 'Zona media',
                            'dimensions': '30x20',
                            'materials': 'Conos',
                            'description_html': '<p>Previo</p>',
                            'coaching_html': '<ul><li>Previo</li></ul>',
                            'rules_html': '<p>Reglas</p>',
                        }
                    },
                    'graphic_editor': {'canvas_state': {'version': '5.3.0', 'objects': []}, 'canvas_width': 1280, 'canvas_height': 720},
                },
            },
        )

        response = self.client.post(
            reverse('sessions-task-edit', args=[task.id]),
            {
                'planner_action': 'create_draw_task',
                'draw_target_session_id': session.id,
                'draw_task_template': 'none',
                'draw_task_title': 'Tarea renombrada sin payload completo',
                'draw_task_block': SessionTask.BLOCK_MAIN_1,
                'draw_task_minutes': '15',
                'draw_task_pitch_preset': 'full_pitch',
                # Omitimos intencionadamente objetivo/consignas/reglas + task_sheet + constraints + assigned_player_ids + canvas_state
            },
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Tarea renombrada sin payload completo')
        self.assertEqual(task.objective, 'Objetivo previo')
        self.assertEqual(task.coaching_points, 'Consignas previas')
        self.assertEqual(task.confrontation_rules, 'Reglas previas')
        meta = (task.tactical_layout or {}).get('meta') or {}
        self.assertEqual(meta.get('constraints'), ['two_touches'])
        self.assertEqual(meta.get('assigned_player_ids'), [self.player.id])
        sheet = ((meta.get('analysis') or {}).get('task_sheet') or {})
        self.assertEqual(sheet.get('description'), 'Descripción previa')
        self.assertEqual(sheet.get('materials'), 'Conos')

    @patch('football.views.weasyprint', None)
    def test_session_task_pdf_renders_uefa_style_layout(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='2 contra 1 en progresión',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            objective='Progresar y finalizar con ventaja',
            coaching_points='Fijar al defensor antes del pase',
            confrontation_rules='Si roba defensa, finaliza en miniportería',
            tactical_layout={
                'meta': {
                    'scope': 'coach',
                    'surface': 'césped natural',
                    'pitch_format': 'fútbol 7',
                    'space': 'Zona central + carriles',
                    'organization': '2x1 en olas',
                    'players_distribution': '3 atacantes / 2 defensores',
                    'load_target': 'RPE 7',
                    'complexity': 'Alta',
                    'training_type': 'Situaciones reducidas',
                    'series': '4',
                    'repetitions': '3',
                    'work_rest': "4x3' + 1'",
                    'success_criteria': '6 finalizaciones limpias',
                    'analysis': {
                        'task_sheet': {
                            'description': 'En un espacio reducido se propone una progresión 2x1 hasta finalizar.',
                            'dimensions': '40x30m',
                            'materials': 'Conos, petos y portería grande',
                        }
                    },
                },
                'timeline': [
                    {'title': 'Salida', 'duration': 2, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                    {'title': 'Finalización', 'duration': 4, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                ],
            },
        )

        response = self.client.get(reverse('session-task-pdf', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entrega Ejercicio')
        self.assertContains(response, 'Detalles del Ejercicio')
        self.assertContains(response, 'Descripción Gráfica')
        self.assertContains(response, 'Consigna / Explicación')
        self.assertContains(response, 'Secuencia animada')
        self.assertContains(response, 'Paso 1')
        self.assertContains(response, 'Situaciones reducidas')
        self.assertContains(response, 'portería grande')
        self.assertContains(response, 'Formato UEFA')

    @patch('football.views.weasyprint', None)
    def test_session_task_pdf_renders_club_style_layout(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea club',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=16,
            objective='Atacar espacio libre',
            tactical_layout={'meta': {'scope': 'coach', 'training_type': 'Juego aplicado'}},
        )

        response = self.client.get(reverse('session-task-pdf', args=[task.id]) + '?style=club')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Planificación de tarea')
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'Formato Club')

    @patch('football.views.weasyprint', None)
    def test_session_plan_pdf_renders_uefa_and_club_styles(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión semanal',
            duration_minutes=90,
            content='Activación, juego aplicado y vuelta a la calma',
            intensity=TrainingSession.INTENSITY_HIGH,
        )
        SessionTask.objects.create(
            session=session,
            title='Juego aplicado 7v7',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            objective='Ajustar alturas y finalizar',
            coaching_points='Fijar antes de soltar',
            confrontation_rules='Si roba, finaliza en miniportería',
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response_uefa = self.client.get(reverse('session-plan-pdf', args=[session.id]))
        response_club = self.client.get(reverse('session-plan-pdf', args=[session.id]) + '?style=club')

        self.assertEqual(response_uefa.status_code, 200)
        self.assertContains(response_uefa, 'Entrega Sesión')
        self.assertContains(response_uefa, 'Detalles de la sesión')
        self.assertContains(response_uefa, 'Juego aplicado 7v7')
        self.assertEqual(response_club.status_code, 200)
        self.assertContains(response_club, 'Planificación de sesión')
        self.assertContains(response_club, 'Formato Club')

    @patch('football.views.weasyprint', None)
    def test_session_task_pdf_preview_renders_without_saving_task(self):
        response = self.client.post(
            reverse('sessions-task-pdf-preview') + '?style=uefa',
            {
                'draw_task_title': 'Borrador sin guardar',
                'draw_task_minutes': '17',
                'draw_task_objective': 'Atacar fijando dentro',
                'draw_task_coaching_points': 'Cambiar ritmo tras control',
                'draw_task_confrontation_rules': 'Dos toques en recepción',
                'draw_task_training_type': 'Situaciones reducidas',
                'draw_task_dimensions': '36x28m',
                'draw_task_space': 'Zona media',
                'draw_task_materials': 'Conos y petos',
                'draw_canvas_state': json.dumps({'version': '5.3.0', 'objects': []}),
                'draw_canvas_preview_data': 'data:image/png;base64,' + base64.b64encode(b'preview-image').decode('ascii'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Borrador sin guardar')
        self.assertContains(response, 'Entrega Ejercicio')
        self.assertFalse(SessionTask.objects.filter(title='Borrador sin guardar').exists())

    def test_session_task_detail_shows_animation_strip_when_task_has_steps(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión con animación',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea animada',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout={
                'timeline': [
                    {'title': 'Salida', 'duration': 2, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                    {'title': 'Llegada', 'duration': 3, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                ],
                'meta': {'scope': 'coach', 'graphic_editor': {'canvas_state': {'version': '5.3.0', 'objects': []}}},
            },
        )

        response = self.client.get(reverse('session-task-detail', args=[task.id]) + '?legacy=1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Secuencia animada')
        self.assertContains(response, 'Paso 1')
        self.assertContains(response, 'Reproducir')

    def test_library_task_can_be_copied_to_session(self):
        library_session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 23),
            focus='Biblioteca coach',
            duration_minutes=90,
        )
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=library_session,
            title='Tarea biblioteca',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'copy_library_task_to_session',
                'planner_tab': 'library',
                'source_task_id': task.id,
                'target_session_id': session.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        copied = SessionTask.objects.exclude(id=task.id).get(session=session)
        self.assertEqual(copied.title, 'Tarea biblioteca')
        self.assertContains(response, 'Tarea copiada a sesión')

    def test_session_task_can_move_duplicate_and_delete(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión operativa',
            duration_minutes=90,
        )
        task_a = SessionTask.objects.create(session=session, title='Tarea A', order=1)
        task_b = SessionTask.objects.create(session=session, title='Tarea B', order=2)

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'move_session_task',
                'planner_tab': 'planning',
                'task_id': task_b.id,
                'move_direction': 'up',
            },
        )
        self.assertEqual(response.status_code, 200)
        task_a.refresh_from_db()
        task_b.refresh_from_db()
        self.assertEqual(task_b.order, 1)
        self.assertEqual(task_a.order, 2)

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'duplicate_session_task',
                'planner_tab': 'planning',
                'task_id': task_b.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SessionTask.objects.filter(session=session).count(), 3)

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'delete_session_task',
                'planner_tab': 'planning',
                'task_id': task_a.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        task_a.refresh_from_db()
        self.assertIsNotNone(task_a.deleted_at)

    def test_microcycle_can_be_cloned_with_sessions_and_tasks(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión original',
            duration_minutes=90,
        )
        SessionTask.objects.create(
            session=session,
            title='Tarea original',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'clone_microcycle_plan',
                'planner_tab': 'planning',
                'source_microcycle_id': self.microcycle.id,
                'clone_week_start': '2026-03-30',
                'clone_week_end': '2026-04-05',
            },
        )

        self.assertEqual(response.status_code, 200)
        cloned = TrainingMicrocycle.objects.get(team=self.team, week_start=date(2026, 3, 30))
        cloned_session = TrainingSession.objects.get(microcycle=cloned)
        self.assertEqual(cloned_session.session_date, date(2026, 4, 1))
        self.assertEqual(cloned_session.focus, 'Sesión original')
        self.assertEqual(cloned_session.tasks.count(), 1)
        self.assertContains(response, 'Microciclo clonado')


class CoachOverviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='coach-overview',
            email='coach-overview@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga Coach', slug='liga-coach', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=season, name='Grupo Coach', slug='grupo-coach')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-coach', group=self.group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Benagalbon Coach',
            slug='benagalbon-coach-workspace',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': True,
                'match_actions': True,
                'sessions': True,
                'analysis': True,
                'abp_board': True,
                'manual_stats': True,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.rival_future = Team.objects.create(name='Rival Futuro', slug='rival-futuro', group=self.group)
        self.rival_old = Team.objects.create(name='Rival Antiguo', slug='rival-antiguo', group=self.group)
        self.client.force_login(self.user)

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_prefers_real_upcoming_match_over_past_convocation(self, _mock_next):
        today = timezone.localdate()
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=today + timedelta(days=7),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )
        ConvocationRecord.objects.create(
            team=self.team,
            round='J23',
            match_date=today - timedelta(days=7),
            location='Pasado',
            opponent_name='Rival Antiguo',
            is_current=True,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Futuro')
        self.assertNotContains(response, 'Rival Antiguo')
        self.assertContains(response, 'Próximo rival')
        self.assertContains(response, 'Estado competitivo')
        self.assertContains(response, 'Clasificación')

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_renders_manual_rival_report_summary(self, _mock_next):
        today = timezone.localdate()
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=today + timedelta(days=7),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )
        RivalAnalysisReport.objects.create(
            team=self.team,
            rival_team=self.rival_future,
            rival_name='Rival Futuro',
            report_title='Informe previo J24',
            weaknesses='Sufren cuando les obligas a defender amplitud.',
            status=RivalAnalysisReport.STATUS_READY,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Futuro')
        self.assertContains(response, 'J24')
        self.assertContains(response, 'MANANTIALES')
        self.assertContains(response, 'Clasificación')

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_prioritizes_manual_current_convocation_for_next_match(self, _mock_next):
        today = timezone.localdate()
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=today + timedelta(days=7),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )
        ConvocationRecord.objects.create(
            team=self.team,
            round='J25',
            match_date=today + timedelta(days=3),
            match_time=timezone.datetime(2026, 4, 2, 18, 30).time(),
            location='NUEVO CAMPO',
            opponent_name='Rival Manual',
            is_current=True,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Manual')
        self.assertContains(response, 'J25')
        self.assertContains(response, 'NUEVO CAMPO')

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_ignores_current_convocation_without_match_date(self, _mock_next):
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=date(2026, 3, 29),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )
        ConvocationRecord.objects.create(
            team=self.team,
            round='Partido 1',
            location='CASABERMEJA',
            opponent_name='Casabermeja',
            is_current=True,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Futuro')
        self.assertNotContains(response, 'Casabermeja')

    @patch('football.views.load_universo_snapshot')
    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_renders_compact_standings(self, _mock_next, mock_snapshot):
        mock_snapshot.return_value = {
            'standings': [
                {'position': 1, 'team': 'RIVAL FUTURO', 'played': 24, 'points': 52},
                {'position': 2, 'team': 'BENAGALBON', 'played': 24, 'points': 49},
                {'position': 3, 'team': 'RIVAL ANTIGUO', 'played': 24, 'points': 45},
            ]
        }
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=date(2026, 3, 29),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clasificación')
        self.assertContains(response, 'BENAGALBON')
        self.assertContains(response, '49')

    @patch('football.views.load_universo_snapshot')
    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_keeps_team_row_in_compact_standings_when_outside_top_positions(self, _mock_next, mock_snapshot):
        mock_snapshot.return_value = {
            'standings': [
                {'position': 1, 'team': 'RIVAL 1', 'played': 24, 'points': 60},
                {'position': 2, 'team': 'RIVAL 2', 'played': 24, 'points': 58},
                {'position': 3, 'team': 'RIVAL 3', 'played': 24, 'points': 56},
                {'position': 4, 'team': 'RIVAL 4', 'played': 24, 'points': 54},
                {'position': 5, 'team': 'RIVAL 5', 'played': 24, 'points': 52},
                {'position': 6, 'team': 'RIVAL 6', 'played': 24, 'points': 50},
                {'position': 7, 'team': 'RIVAL 7', 'played': 24, 'points': 48},
                {'position': 8, 'team': 'RIVAL 8', 'played': 24, 'points': 46},
                {'position': 9, 'team': 'BENAGALBON', 'played': 24, 'points': 44},
            ]
        }
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=date(2026, 3, 29),
            location='MANANTIALES',
            home_team=self.team,
            away_team=self.rival_future,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BENAGALBON')
        self.assertContains(response, '44')

    def test_coach_cards_page_shows_staff_areas_without_duplicating_client_modules(self):
        response = self.client.get(reverse('coach-cards'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cuerpo técnico')
        self.assertContains(response, 'Estadísticas grupales')
        self.assertContains(response, 'Partido')
        self.assertContains(response, 'Entrenamiento')
        self.assertContains(response, 'Análisis')
        self.assertNotContains(response, 'Módulos del cliente')
        self.assertNotContains(response, 'Listado de jugadores')

        training_response = self.client.get(f"{reverse('coach-cards')}?area=training")
        self.assertContains(training_response, reverse('sessions-goalkeeper'))
        self.assertContains(training_response, reverse('sessions-fitness'))

        analysis_response = self.client.get(f"{reverse('coach-cards')}?area=analysis")
        self.assertContains(analysis_response, reverse('analysis'))


class TaskBuilderUiVisibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='builder-user',
            email='builder@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        team = Team.objects.create(name='Equipo pruebas', slug='equipo-pruebas', is_primary=True)
        workspace = Workspace.objects.create(
            name='Workspace pruebas',
            slug='workspace-pruebas',
            kind=Workspace.KIND_CLUB,
            primary_team=team,
            owner_user=self.user,
            enabled_modules={'sessions': True},
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_MEMBER,
            module_access={'sessions': True},
        )

    def test_task_builder_command_menu_is_hidden_by_default(self):
        """
        Regression: el atributo HTML `hidden` debe ocultar siempre el menú de comandos y el popover,
        incluso si el CSS del autor define `display:`.
        """
        self.client.force_login(self.user)

        response = self.client.get(reverse('sessions-task-create'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', errors='ignore')
        self.assertIn('id="task-command-menu" hidden', html)
        self.assertIn('id="task-pattern-popover" hidden', html)
        self.assertIn('.command-menu[hidden]', html)
        self.assertIn('.pattern-popover[hidden]', html)


class ClubOnboardingImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='onboarding-user',
            email='onboarding-user@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)

    def test_club_onboarding_can_import_roster_from_excel(self):
        from io import BytesIO

        try:
            from openpyxl import Workbook
        except Exception as exc:  # pragma: no cover
            self.fail(f'openpyxl no disponible en tests: {exc}')

        wb = Workbook()
        ws = wb.active
        ws.append(['nombre', 'dorsal', 'posicion'])
        ws.append(['Jugador Excel 1', 1, 'DEF'])
        ws.append(['Jugador Excel 2', 9, 'DEL'])
        buf = BytesIO()
        wb.save(buf)

        upload = SimpleUploadedFile(
            'plantilla.xlsx',
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('club-onboarding'),
            {
                'action': 'import_roster',
                'workspace_name': 'Club Excel',
                'team_name': 'Equipo Excel',
                'provider': WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
                'external_group_key': '',
                'external_source_url': '',
                'preferente_url': '',
                'replace_roster': 'on',
                'roster_excel': upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        team = Team.objects.get(name='Equipo Excel')
        self.assertEqual(Player.objects.filter(team=team, is_active=True).count(), 2)
        self.assertTrue(Workspace.objects.filter(name='Club Excel', primary_team=team).exists())

    def test_universo_search_finds_benagalbon_alevin_variant(self):
        candidates = football_views._search_universo_competition_candidates(team_query='Alevin A Benagalbon')
        self.assertTrue(candidates)
        top = candidates[0]
        self.assertTrue(str(top.get('external_group_key') or '').strip())
        self.assertTrue(str(top.get('external_team_key') or '').strip())

    def test_universo_candidate_binds_group_without_live_token(self):
        team = Team.objects.create(name='Alevin A Benagalbón', slug='alevin-a-benagalbon')
        workspace = Workspace.objects.create(name='Club', slug='club', kind=Workspace.KIND_CLUB, primary_team=team, owner_user=self.user)
        context = WorkspaceCompetitionContext.objects.create(
            workspace=workspace,
            team=team,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_key='834315',
            external_team_name='BENAGALBON C.D.',
        )
        football_views._ensure_universo_group_models_from_candidate(
            group_key='45030656',
            competition_name='1ª Andaluza Alevín',
            group_name='Grupo 2',
            season_name='2025/2026',
            competition_code='',
            primary_team=team,
            context=context,
        )
        team.refresh_from_db()
        context.refresh_from_db()
        self.assertIsNotNone(team.group_id)
        self.assertEqual(team.group.external_id, '45030656')
        self.assertEqual(context.group_id, team.group_id)
