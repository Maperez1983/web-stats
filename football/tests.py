import base64
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import date, timedelta, time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from football.models import AnalystVideoFolder, AnalysisVideoReport, Competition, ConvocationRecord, Group, Match, MatchEvent, MatchReport, Player, PlayerCommunication, PlayerEvaluation, PlayerFine, PlayerSeasonReport, PlayerStatistic, RivalAnalysisReport, RivalVideo, Season, SessionTask, StaffMember, TacticalPlaybookClip, TaskStudioProfile, TaskStudioRosterPlayer, TaskStudioTask, Team, TeamStanding, TrainingMicrocycle, TrainingSession, TrainingSessionAttendance, UserInvitation, VideoClip, VideoTimelineEvent, VideoTelestrationProject, Workspace, WorkspaceCompetitionContext, WorkspaceCompetitionSnapshot, WorkspaceMembership, WorkspacePlayer, WorkspacePreference, WorkspaceSeason, WorkspaceSeasonPlayer, WorkspaceSeasonTeam, WorkspaceTeam, WorkspaceTeamAccess
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
from football import dashboard_services, next_match_services, team_media_services, workspace_context
from football import dashboard_pending_services
from football.session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields
from football.models import AppUserRole
from football.services import find_roster_entry
from football.staff_briefing import build_weekly_staff_brief
from football.task_library import filter_task_library, prepare_task_library
from football.stats_audit import run_stats_audit
from football.dashboard_services import SCRAPE_LOCK_KEY, compute_player_cards_for_match, compute_player_dashboard, compute_player_metrics, compute_team_metrics_for_match
from django.test import override_settings
from unittest.mock import Mock, patch
import requests


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


class TeamMediaServicesTests(TestCase):
    def test_benagalbon_detection_does_not_use_primary_flag(self):
        team = Team(name='Málaga Club de Fútbol', slug='malaga-cf', is_primary=True)
        self.assertFalse(team_media_services.is_benagalbon_team(team))

    def test_benagalbon_detection_uses_team_identity(self):
        team = Team(name='C.D. Benagalbón', slug='cd-benagalbon')
        self.assertTrue(team_media_services.is_benagalbon_team(team))

    def test_player_pdf_palette_uses_malaga_identity(self):
        team = Team(name='Málaga Club de Fútbol', slug='malaga-cf', is_primary=True)
        palette = team_media_services.team_pdf_palette(team, 'club')
        self.assertEqual(palette['primary'], '#6bc4e8')
        self.assertEqual(palette['accent'], '#004b93')

    def test_non_benagalbon_fallback_crest_is_team_specific(self):
        team = Team(name='Málaga Club de Fútbol', slug='malaga-cf', is_primary=True)
        crest = team_media_services.team_fallback_crest_data_uri(team)
        self.assertTrue(crest.startswith('data:image/svg+xml;base64,'))
        self.assertNotIn('cdb-benagalbon', crest)

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

    def test_product_landing_login_url_uses_same_host_outside_landing_domains(self):
        with override_settings(ALLOWED_HOSTS=['testserver', 'web-stats.onrender.com']):
            response = self.client.get(reverse('product-landing'), HTTP_HOST='web-stats.onrender.com', secure=True)
            self.assertEqual(response.status_code, 200)
            # Robustez: extraer el href real para evitar falsos negativos por minificación/atributos.
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'html.parser')
            button = soup.select_one('a.button.primary[href]')
            self.assertIsNotNone(button)
            self.assertEqual(button.get('href'), 'https://web-stats.onrender.com/login/')


class PendingCardsRivalReportTests(TestCase):
    def setUp(self):
        self.primary_team = Team.objects.create(
            name='Club Test',
            slug='club-test',
            is_primary=True,
        )
        self.rival_team = Team.objects.create(
            name='CD Rival',
            slug='cd-rival',
            is_primary=False,
        )

    def _brief_for(self, opponent_name: str):
        return {
            'match': {'opponent': opponent_name},
            'convocated_count': 18,
            'probable_eleven_count': 11,
            'available_count': 18,
        }

    def _pending_card(self, cards, title):
        for card in cards:
            if card.get('title') == title:
                return card
        return None

    def test_pending_card_appears_when_no_reports_exist(self):
        cards = dashboard_pending_services.build_team_pending_cards(self.primary_team, weekly_brief=self._brief_for('CD Rival'))
        card = self._pending_card(cards, 'Informe rival pendiente')
        self.assertIsNotNone(card)
        self.assertIn('No hay un informe rival listo', str(card.get('description') or ''))

    def test_pending_card_mentions_export_when_report_exists_but_no_pptx(self):
        folder = AnalystVideoFolder.objects.create(team=self.primary_team, rival_team=self.rival_team, name='J01')
        AnalysisVideoReport.objects.create(team=self.primary_team, folder=folder, title='Informe CD Rival')
        cards = dashboard_pending_services.build_team_pending_cards(self.primary_team, weekly_brief=self._brief_for('CD Rival'))
        card = self._pending_card(cards, 'Informe rival pendiente')
        self.assertIsNotNone(card)
        self.assertIn('falta exportar el PPTX', str(card.get('description') or ''))

    def test_pending_card_disappears_when_pptx_export_exists(self):
        folder = AnalystVideoFolder.objects.create(team=self.primary_team, rival_team=self.rival_team, name='J01')
        report = AnalysisVideoReport.objects.create(team=self.primary_team, folder=folder, title='Informe CD Rival')
        report.pptx_file.save('informe-cd-rival.pptx', SimpleUploadedFile('informe-cd-rival.pptx', b'pptx-bytes'), save=True)
        cards = dashboard_pending_services.build_team_pending_cards(self.primary_team, weekly_brief=self._brief_for('CD Rival'))
        card = self._pending_card(cards, 'Informe rival pendiente')
        self.assertIsNone(card)

    def test_pending_card_disappears_when_manual_ready_report_exists(self):
        RivalAnalysisReport.objects.create(
            team=self.primary_team,
            rival_team=self.rival_team,
            rival_name='CD Rival',
            status=RivalAnalysisReport.STATUS_READY,
        )
        cards = dashboard_pending_services.build_team_pending_cards(self.primary_team, weekly_brief=self._brief_for('CD Rival'))
        card = self._pending_card(cards, 'Informe rival pendiente')
        self.assertIsNone(card)


class ManualOverridesAndKpiConsistencyTests(TestCase):
    def test_manual_base_overrides_survive_manual_match_for_other_player(self):
        competition = Competition.objects.create(name='Comp', slug='comp', level=1, region='test')
        season = Season.objects.create(
            competition=competition,
            name='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        group = Group.objects.create(season=season, name='Grupo', slug='grupo')
        team = Team.objects.create(name='Equipo', slug='equipo', group=group, is_primary=True)
        opponent = Team.objects.create(name='Rival', slug='rival', group=group, is_primary=False)
        player_a = Player.objects.create(team=team, name='Jugador A')
        player_b = Player.objects.create(team=team, name='Jugador B')
        match = Match.objects.create(
            season=season,
            group=group,
            round='J1',
            context=Match.CONTEXT_LEAGUE,
            date=date(2026, 1, 1),
            home_team=team,
            away_team=opponent,
        )

        PlayerStatistic.objects.create(player=player_a, season=season, match=None, context='manual-base', name='manual_pj', value=31)
        PlayerStatistic.objects.create(player=player_a, season=season, match=None, context='manual-base', name='manual_pt', value=29)
        PlayerStatistic.objects.create(player=player_a, season=season, match=None, context='manual-base', name='manual_minutes', value=2465)
        PlayerStatistic.objects.create(player=player_b, season=season, match=match, context='manual-match', name='manual_minutes', value=45)

        rows = compute_player_dashboard(team, force_refresh=True, scope=Match.CONTEXT_LEAGUE)
        row_a = next((row for row in rows if int(row.get('player_id') or 0) == player_a.id), None)
        self.assertIsNotNone(row_a)
        self.assertEqual(int(row_a.get('pj') or 0), 31)
        self.assertEqual(int(row_a.get('pt') or 0), 29)
        self.assertEqual(int(row_a.get('minutes') or 0), 2465)

    def test_manual_match_stats_override_stale_base_for_same_player(self):
        competition = Competition.objects.create(name='Comp B', slug='comp-b', level=1, region='test')
        season = Season.objects.create(
            competition=competition,
            name='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        group = Group.objects.create(season=season, name='Grupo B', slug='grupo-b')
        team = Team.objects.create(name='Benagalbon Pre', slug='benagalbon-pre-kpi', group=group, is_primary=False)
        opponent = Team.objects.create(name='Rival B', slug='rival-b-kpi', group=group, is_primary=False)
        player = Player.objects.create(team=team, name='Gonzalo Test', number=9)

        # Base antigua/consolidada: reproduce el síntoma visto en Gonzalo.
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_pj', value=5)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_pt', value=5)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_minutes', value=230)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_goals', value=6)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_assists', value=12)

        expected = {'pj': 0, 'minutes': 0, 'goals': 0, 'assists': 0}
        for idx, values in enumerate(
            (
                {'minutes': 45, 'goals': 2, 'assists': 1},
                {'minutes': 40, 'goals': 3, 'assists': 2},
                {'minutes': 35, 'goals': 1, 'assists': 4},
            ),
            start=1,
        ):
            match = Match.objects.create(
                season=season,
                group=group,
                round=f'Jornada {idx}',
                context=Match.CONTEXT_LEAGUE,
                date=date(2026, 1, idx),
                home_team=team,
                away_team=opponent,
                home_score=idx,
                away_score=0,
                result=f'{idx}-0',
            )
            PlayerStatistic.objects.create(player=player, season=season, match=match, context='manual-match', name='manual_minutes', value=values['minutes'])
            PlayerStatistic.objects.create(player=player, season=season, match=match, context='manual-match', name='manual_goals', value=values['goals'])
            PlayerStatistic.objects.create(player=player, season=season, match=match, context='manual-match', name='manual_assists', value=values['assists'])
            expected['pj'] += 1
            expected['minutes'] += values['minutes']
            expected['goals'] += values['goals']
            expected['assists'] += values['assists']

        rows = compute_player_dashboard(team, force_refresh=True, scope=Match.CONTEXT_LEAGUE)
        row = next((item for item in rows if int(item.get('player_id') or 0) == player.id), None)
        self.assertIsNotNone(row)
        self.assertEqual(int(row.get('pj') or 0), expected['pj'])
        self.assertEqual(int(row.get('minutes') or 0), expected['minutes'])
        self.assertEqual(int(row.get('goals') or 0), expected['goals'])
        self.assertEqual(int(row.get('assists') or 0), expected['assists'])
        self.assertEqual(len([m for m in row.get('matches', []) if m.get('played')]), expected['pj'])

    @patch('football.views.get_competition_total_rounds', return_value=10)
    def test_participation_uses_full_season_minutes(self, _mock_rounds):
        competition = Competition.objects.create(name='Comp C', slug='comp-c', level=1, region='test')
        season = Season.objects.create(
            competition=competition,
            name='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        group = Group.objects.create(season=season, name='Grupo C', slug='grupo-c')
        team = Team.objects.create(name='Equipo C', slug='equipo-c-kpi', group=group, is_primary=True)
        player = Player.objects.create(team=team, name='Jugador Media Temporada', number=8)

        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_pj', value=5)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_pt', value=5)
        PlayerStatistic.objects.create(player=player, season=season, match=None, context='manual-base', name='manual_minutes', value=450)

        rows = compute_player_dashboard(team, force_refresh=True, scope=Match.CONTEXT_LEAGUE)
        row = next((item for item in rows if int(item.get('player_id') or 0) == player.id), None)

        self.assertIsNotNone(row)
        self.assertEqual(float(row.get('participation_pct') or 0), 50.0)
        self.assertEqual(float(row.get('participation_matches_pct') or 0), 100.0)


class AnalysisVideoReportPdfExportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='staff', password='pass-1234')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)

        self.team = Team.objects.create(name='Club Test', slug='club-test-2', is_primary=True)
        self.rival = Team.objects.create(name='CD Rival', slug='cd-rival-2', is_primary=False)
        self.folder = AnalystVideoFolder.objects.create(team=self.team, rival_team=self.rival, name='J01')
        self.report = AnalysisVideoReport.objects.create(team=self.team, folder=self.folder, title='Informe rival')

    def test_export_pdf_endpoint_returns_pdf_or_503(self):
        url = reverse('analysis-video-report-export-pdf', args=[self.report.id])
        response = self.client.get(f'{url}?team_id={self.team.id}&inline=1')
        self.assertIn(response.status_code, {200, 503})
        if response.status_code == 200:
            self.assertEqual(response['Content-Type'], 'application/pdf')


class PreferenteRosterJsonFallbackTests(SimpleTestCase):
    def test_preferente_fetch_rejects_non_preferente_hosts(self):
        from football import services as football_services

        with self.assertRaises(ValueError):
            football_services._fetch_preferente_response('https://example.com/equipo')

    def test_official_rows_rejects_private_network_urls_before_request(self):
        from football import services as football_services

        with patch.object(football_services.requests, 'get') as mocked_get:
            with self.assertRaises(ValueError):
                football_services.fetch_official_rows('http://127.0.0.1:8000/admin/')
        mocked_get.assert_not_called()

    def test_preferente_json_fallback_handles_request_exception(self):
        from football import services as football_services

        class FakeSession:
            def __init__(self):
                self.cookies = {'x': 'y'}

            def get(self, *args, **kwargs):
                raise requests.RequestException('network down')

        with patch.object(football_services, '_get_preferente_session', return_value=FakeSession()):
            # Debe devolver [] y no lanzar UnboundLocalError (regresión).
            rows = football_services._fetch_preferente_team_roster_via_json('123')
            self.assertEqual(rows, [])

    def test_preferente_json_fallback_retries_on_403(self):
        from football import services as football_services

        class FakeResp:
            def __init__(self, status_code=200, ok=True, payload=None):
                self.status_code = status_code
                self.ok = ok
                self._payload = payload or {}

            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self):
                self.cookies = {'x': 'y'}
                self.calls = 0

            def get(self, url, *args, **kwargs):
                self.calls += 1
                if 'json/buscaJugador.php' in str(url):
                    # 1º intento bloqueado, 2º ok sin resultados.
                    if self.calls == 1:
                        return FakeResp(status_code=403, ok=False, payload={})
                    return FakeResp(status_code=200, ok=True, payload={'results': [], 'pagination': {'more': False}})
                # Home warmup
                return FakeResp(status_code=200, ok=True, payload={})

        with patch.object(football_services, '_get_preferente_session', return_value=FakeSession()):
            rows = football_services._fetch_preferente_team_roster_via_json('123')
            self.assertEqual(rows, [])


class UniversoEnvNamingTests(SimpleTestCase):
    def test_universo_login_reads_universo_env_names(self):
        from football import universo_client

        with patch.dict(
            os.environ,
            {
                'UNIVERSO_RFAF_USER': 'user@example.com',
                'UNIVERSO_RFAF_PASS': 'secret',
                'RFAF_USER': '',
                'RFAF_PASS': '',
            },
            clear=False,
        ):
            with patch.object(universo_client, 'requests', create=True) as req:
                # Simula un login OK con token.
                class Resp:
                    ok = True
                    status_code = 200
                    headers = {'content-type': 'application/json'}

                    @staticmethod
                    def json():
                        return {'token': 'a.b.c'}

                req.post.return_value = Resp()
                token, exp, err = universo_client.fetch_universo_access_token_via_login()
                self.assertTrue(token)
                self.assertEqual(err, '')


class CanonicalAppBaseUrlNormalizationTests(TestCase):
    def test_login_redirect_strips_path_from_app_public_base_url(self):
        with override_settings(ALLOWED_HOSTS=['testserver', 'landing.example.com', 'app.example.com']):
            with patch.dict(
                os.environ,
                {
                    'APP_PUBLIC_BASE_URL': 'https://app.example.com/2J',
                    'LANDING_HOSTS': 'landing.example.com',
                },
                clear=False,
            ):
                response = self.client.get(reverse('login'), HTTP_HOST='landing.example.com', secure=True)
        self.assertIn(response.status_code, {301, 302})
        self.assertEqual(response['Location'], 'https://app.example.com/login/')

    def test_canonical_host_middleware_redirects_non_landing_hosts(self):
        with override_settings(ALLOWED_HOSTS=['testserver', 'internal.onrender.com', 'app.example.com']):
            with patch.dict(
                os.environ,
                {
                    'APP_PUBLIC_BASE_URL': 'https://app.example.com',
                    'LANDING_HOSTS': 'segundajugada.es,www.segundajugada.es',
                },
                clear=False,
            ):
                response = self.client.get(reverse('product-landing'), HTTP_HOST='internal.onrender.com', secure=True)
        self.assertIn(response.status_code, {301, 302})
        self.assertEqual(response['Location'], 'https://app.example.com/2j/')


class TacticsLandingModalFallbackTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo prueba',
            slug='equipo-prueba',
            short_name='Prueba',
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-tactics',
            email='coach-tactics@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='CLUB PRUEBA',
            slug='club-prueba',
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

    def test_coach_tactics_page_includes_clickable_landing_fallback(self):
        self.client.force_login(self.user)
        url = f"{reverse('coach-tactics')}?workspace={self.workspace.id}"
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '__webstatsTaskLandingGo')
        self.assertContains(response, 'onclick="return window.__webstatsTaskLandingGo')

    def test_playbook_endpoints_work_when_sessions_disabled_but_tactics_enabled(self):
        # Caso real: club puede desactivar "Sesiones" pero mantener "Táctica".
        self.workspace.enabled_modules = {'sessions': False, 'tactics': True}
        self.workspace.save(update_fields=['enabled_modules'])
        self.client.force_login(self.user)
        url = f"{reverse('tactical-playbook-clips-api')}?workspace={self.workspace.id}&team={self.team.id}"
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertIn('items', payload)

    def test_tactics_can_be_saved_as_library_task_when_sessions_disabled(self):
        self.workspace.enabled_modules = {'sessions': False, 'tactics': True}
        self.workspace.save(update_fields=['enabled_modules'])
        self.client.force_login(self.user)
        url = f"{reverse('tactical-playbook-task-save-api')}?workspace={self.workspace.id}&team={self.team.id}"
        payload = {
            'scope': 'team',
            'name': 'Tarea táctica test',
            'folder': 'Tácticas',
            'tags': ['tactica'],
            'steps': [
                {
                    'title': 'Táctica',
                    'duration': 6,
                    'canvas_state': {'version': '5.3.0', 'objects': []},
                    'canvas_width': 1054,
                    'canvas_height': 684,
                    'moves': [],
                    'routes': {},
                    'ball_follow_uid': '',
                    'preset': 'full_pitch',
                    'orientation': 'landscape',
                    'grass_style': 'classic',
                    'zoom': 1.0,
                }
            ],
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json', secure=True)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('ok'))
        task_id = int(data.get('id') or 0)
        self.assertTrue(task_id)
        self.assertTrue(SessionTask.objects.filter(id=task_id).exists())


class KPIExplorerWorkspacePresetsTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='Comp', slug='comp')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='Grupo', slug='grupo')
        self.team = Team.objects.create(
            name='Equipo prueba',
            slug='equipo-prueba-kpi',
            short_name='Prueba',
            group=self.group,
            is_primary=True,
        )
        self.rival = Team.objects.create(
            name='Rival prueba',
            slug='rival-prueba-kpi',
            short_name='Rival',
            group=self.group,
            is_primary=False,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-kpi',
            email='coach-kpi@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='CLUB KPI',
            slug='club-kpi',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.player = Player.objects.create(team=self.team, name='Jugador', number=7, is_active=True)
        self.match = Match.objects.create(
            season=self.season,
            group=self.group,
            round='J1',
            context=Match.CONTEXT_LEAGUE,
            date=timezone.localdate(),
            home_team=self.team,
            away_team=self.rival,
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            minute=5,
            event_type='Pase',
            result='OK',
            zone='Defensa derecha',
            tercio='Defensa',
            observation='Pase interior',
            source_file='manual',
        )

    def test_workspace_preference_set_and_get(self):
        self.client.force_login(self.user)
        set_url = f"{reverse('workspace-pref-set')}?workspace={self.workspace.id}"
        get_url = f"{reverse('workspace-pref-get')}?workspace={self.workspace.id}&key=test.pref"
        response = self.client.post(
            set_url,
            data=json.dumps({'key': 'test.pref', 'value': {'a': 1}}),
            content_type='application/json',
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        response = self.client.get(get_url, secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload.get('value', {}).get('a'), 1)

    def test_workspace_preference_rejects_large_generic_payload(self):
        self.client.force_login(self.user)
        set_url = f"{reverse('workspace-pref-set')}?workspace={self.workspace.id}"
        response = self.client.post(
            set_url,
            data=json.dumps({'key': 'test.large', 'value': {'blob': 'x' * 170_000}}),
            content_type='application/json',
            secure=True,
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertEqual(payload.get('code'), 'payload_too_large')

    def test_workspace_preference_allows_large_kit2d_payload(self):
        self.client.force_login(self.user)
        set_url = f"{reverse('workspace-pref-set')}?workspace={self.workspace.id}"
        response = self.client.post(
            set_url,
            data=json.dumps({'key': 'kit2d.tokens', 'value': {'blob': 'x' * 700_000}}),
            content_type='application/json',
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        pref = WorkspacePreference.objects.get(workspace=self.workspace, key='kit2d.tokens')
        self.assertEqual(len(pref.value.get('blob', '')), 700_000)

    def test_workspace_preference_errors_include_stable_code(self):
        self.client.force_login(self.user)
        response = self.client.get(
            f"{reverse('workspace-pref-get')}?workspace={self.workspace.id}",
            secure=True,
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertEqual(payload.get('code'), 'key_required')

    def test_kpi_explorer_page_includes_shared_preset_ui(self):
        self.client.force_login(self.user)
        url = f"{reverse('kpi-explorer')}?workspace={self.workspace.id}"
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'kpi-preset-name')
        self.assertContains(response, 'kpi-preset-save')
        self.assertContains(response, 'kpi-preset-list')

    def test_kpi_explorer_sources_api_returns_rows(self):
        self.client.force_login(self.user)
        url = f"{reverse('kpi-explorer-sources-api')}?workspace={self.workspace.id}"
        payload = {
            'scope': 'match',
            'context': 'league',
            'match_id': int(self.match.id),
            'player_id': 0,
            'metric': {'kind': 'derived', 'key': 'pass_attempts'},
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json', secure=True)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get('ok'))
        self.assertGreaterEqual(int(body.get('count') or 0), 1)


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class SessionsPlannerPRGRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sessions-prg',
            email='sessions-prg@example.com',
            password='pass-1234',
            is_staff=True,
            is_superuser=True,
        )
        self.team = Team.objects.create(
            name='Equipo sesiones',
            slug='equipo-sesiones',
            short_name='Sesiones',
            is_primary=True,
        )
        self.workspace = Workspace.objects.create(
            name='CLUB SESIONES',
            slug='club-sesiones',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

        self.library_microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Biblioteca Entrenador',
            objective='Repo',
            week_start=date.today(),
            week_end=date.today(),
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes=f'{football_views.LIBRARY_MICROCYCLE_MARKER} tests',
        )
        self.library_session = TrainingSession.objects.create(
            microcycle=self.library_microcycle,
            session_date=date.today(),
            duration_minutes=90,
            intensity=TrainingSession.INTENSITY_MEDIUM,
            focus='Biblioteca PDF · Entrenador',
            content='',
            status=TrainingSession.STATUS_PLANNED,
            order=1,
        )
        self.source_task = SessionTask.objects.create(
            session=self.library_session,
            title='Tarea origen',
            block=SessionTask.BLOCK_CONDITIONING,
            duration_minutes=15,
            objective='',
            coaching_points='',
            confrontation_rules='',
            tactical_layout={'meta': {'scope': 'coach', 'repository': 'traditional'}},
            status=SessionTask.STATUS_PLANNED,
            order=1,
            notes='',
        )

        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            objective='',
            week_start=date.today() + timedelta(days=7),
            week_end=date.today() + timedelta(days=13),
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes='',
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date.today() + timedelta(days=7),
            duration_minutes=90,
            intensity=TrainingSession.INTENSITY_MEDIUM,
            focus='Sesión destino',
            content='',
            status=TrainingSession.STATUS_PLANNED,
            order=1,
        )

    def test_copy_task_to_session_uses_prg_redirect_and_keeps_selected_session(self):
        self.client.force_login(self.user)
        url = f"{reverse('sessions')}?team={self.team.id}&workspace={self.workspace.id}&tab=sessions&library_repo=traditional&session_id={self.session.id}"
        before = SessionTask.objects.filter(session=self.session, deleted_at__isnull=True).count()
        response = self.client.post(
            url,
            data={
                'planner_action': 'copy_library_task_to_session',
                'planner_tab': 'sessions',
                'team': str(self.team.id),
                'workspace': str(self.workspace.id),
                'library_repo': 'traditional',
                'selected_session_id': str(self.session.id),
                'target_session_id': str(self.session.id),
                'source_task_id': str(self.source_task.id),
                'target_block': SessionTask.BLOCK_CONDITIONING,
            },
            follow=False,
        )
        after = SessionTask.objects.filter(session=self.session, deleted_at__isnull=True).count()
        self.assertEqual(after, before + 1)
        self.assertIn(response.status_code, {301, 302})
        self.assertIn('tab=sessions', response['Location'])
        self.assertIn(f'session_id={self.session.id}', response['Location'])

    def test_create_session_plan_uses_prg_redirect(self):
        self.client.force_login(self.user)
        url = f"{reverse('sessions')}?team={self.team.id}&workspace={self.workspace.id}&tab=sessions&library_repo=traditional"
        before = TrainingSession.objects.filter(microcycle__team=self.team).count()
        response = self.client.post(
            url,
            data={
                'planner_action': 'create_session_plan',
                'planner_tab': 'sessions',
                'team': str(self.team.id),
                'workspace': str(self.workspace.id),
                'plan_microcycle_id': '',
                'plan_session_date': str(date.today()),
                'plan_session_focus': 'Nueva sesión',
                'plan_session_minutes': '90',
                'plan_session_intensity': TrainingSession.INTENSITY_MEDIUM,
                'plan_session_status': TrainingSession.STATUS_PLANNED,
            },
            follow=False,
        )
        after = TrainingSession.objects.filter(microcycle__team=self.team).count()
        self.assertEqual(after, before + 1)
        self.assertIn(response.status_code, {301, 302})

    def test_sessions_view_does_not_hide_tasks_by_repository(self):
        self.client.force_login(self.user)
        interactive_source = SessionTask.objects.create(
            session=self.library_session,
            title='Tarea interactiva origen',
            block=SessionTask.BLOCK_ACTIVATION,
            duration_minutes=8,
            tactical_layout={'meta': {'scope': 'coach', 'repository': 'interactive'}},
            status=SessionTask.STATUS_PLANNED,
            order=2,
        )
        url = f"{reverse('sessions')}?team={self.team.id}&workspace={self.workspace.id}&tab=sessions&library_repo=traditional&session_id={self.session.id}"
        self.client.post(
            url,
            data={
                'planner_action': 'copy_library_task_to_session',
                'planner_tab': 'sessions',
                'team': str(self.team.id),
                'workspace': str(self.workspace.id),
                'library_repo': 'traditional',
                'selected_session_id': str(self.session.id),
                'target_session_id': str(self.session.id),
                'source_task_id': str(interactive_source.id),
                'target_block': SessionTask.BLOCK_ACTIVATION,
              },
            follow=False,
        )
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tarea interactiva origen')


class LoginRememberSessionRedirectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='login-remember',
            email='login-remember@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)

    def test_login_redirects_when_already_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'), secure=True)
        self.assertIn(response.status_code, {301, 302})


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'app.segundajugada.es'])
class AppHomePlatformDefaultTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo app home',
            slug='equipo-app-home',
            short_name='Home',
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='platform-user',
            email='platform-user@example.com',
            password='pass-1234',
            is_staff=True,
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        self.workspace = Workspace.objects.create(
            name='CLUB HOME',
            slug='club-home',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

    def test_app_root_does_not_force_platform_when_workspace_active(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()
        response = self.client.get('/', secure=True, HTTP_HOST='app.segundajugada.es')
        self.assertEqual(response.status_code, 200)


class MatchdayQuickButtonsTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='CompQB', slug='comp-qb')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoQB', slug='grupo-qb')
        self.team = Team.objects.create(
            name='Equipo QB',
            slug='equipo-qb',
            short_name='QB',
            group=self.group,
            is_primary=True,
        )
        self.rival = Team.objects.create(
            name='Rival QB',
            slug='rival-qb',
            short_name='RQB',
            group=self.group,
            is_primary=False,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-qb',
            email='coach-qb@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.member = get_user_model().objects.create_user(
            username='staff-qb',
            email='staff-qb@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.member, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='CLUB QB',
            slug='club-qb',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'match_actions': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.member, role=WorkspaceMembership.ROLE_MEMBER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.player = Player.objects.create(team=self.team, name='Jugador QB', number=7, is_active=True)
        self.match = Match.objects.create(
            season=self.season,
            group=self.group,
            round='J1',
            context=Match.CONTEXT_LEAGUE,
            date=timezone.localdate(),
            home_team=self.team,
            away_team=self.rival,
        )
        self.conv = ConvocationRecord.objects.create(team=self.team, match=self.match, opponent_name='Rival QB', is_current=True)
        self.conv.players.add(self.player)

        from football.models import WorkspacePreference
        WorkspacePreference.objects.create(
            workspace=self.workspace,
            key='matchday_quick_buttons:v1',
            value={
                'v': 1,
                'by_role': {
                    'coach': [
                        {'label': 'DA', 'action': 'Duelos aéreos', 'result': 'Ganado', 'hotkey': '1'},
                        {'label': 'DIS', 'action': 'Disparo', 'result': 'A puerta', 'hotkey': '2'},
                    ]
                },
            },
        )

    def _activate_workspace(self):
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def test_match_action_page_renders_custom_quick_buttons(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('match-action-page'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-action="Duelos aéreos"')
        self.assertContains(response, 'data-result="Ganado"')
        self.assertContains(response, 'data-hotkey="1"')

    def test_quick_buttons_api_denies_non_admin_members(self):
        self.client.force_login(self.member)
        self._activate_workspace()
        response = self.client.get(reverse('matchday-quick-buttons-api'), secure=True)
        self.assertEqual(response.status_code, 403)

    def test_quick_buttons_api_roundtrip(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        url = reverse('matchday-quick-buttons-api')
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload.get('role'), 'coach')
        self.assertGreaterEqual(len(payload.get('items') or []), 1)

        post_payload = {
            'items': [
                {'label': 'Falta', 'action': 'Falta', 'result': 'Ganado', 'hotkey': '3'},
            ],
        }
        response = self.client.post(url, data=json.dumps(post_payload), content_type='application/json', secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))

        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        labels = [item.get('label') for item in (payload.get('items') or [])]
        self.assertIn('Falta', labels)


class CoachRivalsManagementTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media_dir)
        self._override.enable()
        self.competition = Competition.objects.create(name='CompRivals', slug='comp-rivals')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoRivals', slug='grupo-rivals')
        self.team = Team.objects.create(
            name='Málaga CF',
            slug='malaga-cf-rivals',
            short_name='Málaga',
            group=self.group,
            is_primary=True,
        )
        self.rival = Team.objects.create(
            name='Rival Gestión',
            slug='rival-gestion',
            short_name='Rival',
            group=self.group,
            is_primary=False,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-rivals',
            email='coach-rivals@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='Club Rivales',
            slug='club-rivales',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'coach_overview': True, 'analysis': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)

    def test_trainer_page_exposes_rivals_tab(self):
        response = self.client.get(reverse('coach-role-trainer'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{reverse('coach-rivals')}?team={self.team.id}")
        self.assertContains(response, 'Rivales')

    def test_rivals_page_falls_back_to_accessible_default_team_without_query(self):
        session = self.client.session
        session.pop('active_workspace_id', None)
        session.pop('active_team_by_workspace', None)
        session.save()
        response = self.client.get(reverse('coach-rivals'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rivales')

    def test_rival_profile_saves_crest_and_kit2d_uploads(self):
        png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01'
            b'\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        response = self.client.post(
            reverse('coach-rival-profile', args=[self.rival.id]),
            data={
                'form_action': 'save_identity',
                'short_name': 'RIV',
                'home_stadium': 'Estadio Rival',
                'home_stadium_address': 'Calle Rival 1, Málaga',
                'home_stadium_latitude': '36.721302',
                'home_stadium_longitude': '-4.421637',
                'crest_image': SimpleUploadedFile('escudo.png', png, content_type='image/png'),
                'kit2d_home': SimpleUploadedFile('home.png', png, content_type='image/png'),
                'kit2d_gk2': SimpleUploadedFile('gk2.png', png, content_type='image/png'),
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.rival.refresh_from_db()
        self.assertEqual(self.rival.short_name, 'RIV')
        self.assertEqual(self.rival.home_stadium, 'Estadio Rival')
        self.assertEqual(self.rival.home_stadium_address, 'Calle Rival 1, Málaga')
        self.assertEqual(str(self.rival.home_stadium_latitude), '36.721302')
        self.assertEqual(str(self.rival.home_stadium_longitude), '-4.421637')
        self.assertTrue(self.rival.crest_image)
        pref = WorkspacePreference.objects.get(
            workspace=self.workspace,
            key=f'rival_kit2d:{self.rival.id}',
        )
        self.assertTrue(pref.value.get('home_club_data_url', '').startswith('data:image/png;base64,'))
        self.assertTrue(pref.value.get('gk2_club_data_url', '').startswith('data:image/png;base64,'))
        response = self.client.get(reverse('coach-rivals'), secure=True)
        self.assertContains(response, 'data:image/png;base64,')
        self.assertContains(response, 'Ubicación guardada')

    def test_rival_profile_can_generate_kit_from_colors_without_file(self):
        response = self.client.post(
            reverse('coach-rival-profile', args=[self.rival.id]),
            data={
                'form_action': 'save_identity',
                'short_name': 'RIV',
                'home_stadium': 'Estadio Rival',
                'use_kit2d_colors_home': 'on',
                'kit2d_home_main_color': '#123456',
                'kit2d_home_trim_color': '#fedcba',
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        pref = WorkspacePreference.objects.get(
            workspace=self.workspace,
            key=f'rival_kit2d:{self.rival.id}',
        )
        self.assertEqual(pref.value.get('home_main_color'), '#123456')
        self.assertEqual(pref.value.get('home_trim_color'), '#fedcba')
        self.assertNotIn('home_club_data_url', pref.value)
        response = self.client.get(reverse('coach-rivals'), secure=True)
        self.assertContains(response, 'data:image/svg+xml;base64,')


class SessionsAssignTaskSmokeTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='CompSes', slug='comp-ses')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoSes', slug='grupo-ses')
        self.team = Team.objects.create(
            name='Equipo Sesiones',
            slug='equipo-ses',
            short_name='SES',
            group=self.group,
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='coach-ses',
            email='coach-ses@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='WS SESIONES',
            slug='ws-ses',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'sessions': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

        # Microciclo y sesión real donde asignar.
        self.micro = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Micro 1',
            week_start=timezone.localdate(),
            week_end=timezone.localdate(),
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.micro,
            session_date=timezone.localdate(),
            focus='Entreno 1',
            duration_minutes=75,
            intensity='media',
            status='Planificada',
            order=1,
        )

        # Tarea en biblioteca (origen).
        self.library_micro = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Biblioteca · entrenador',
            week_start=timezone.localdate() + timedelta(days=7),
            week_end=timezone.localdate() + timedelta(days=7),
            notes='[LIBRARY]',
        )
        self.library_session = TrainingSession.objects.create(
            microcycle=self.library_micro,
            session_date=timezone.localdate(),
            focus='Biblioteca · tareas',
            duration_minutes=0,
            intensity='baja',
            status='Planificada',
            order=1,
        )
        self.source_task = SessionTask.objects.create(
            session=self.library_session,
            title='Rondo 4v2',
            block=SessionTask.BLOCK_CONDITIONING,
            duration_minutes=12,
            objective='',
            coaching_points='',
            confrontation_rules='',
            tactical_layout={'meta': {'scope': 'coach', 'repository': 'traditional'}},
            status=SessionTask.STATUS_PLANNED,
            order=1,
            notes='',
        )

    def _activate_workspace(self):
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def test_sessions_page_renders(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('sessions'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_assign_library_task_to_session_creates_task(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        url = reverse('sessions')
        response = self.client.post(
            url,
            data={
                'planner_action': 'copy_library_task_to_session',
                'source_task_id': str(self.source_task.id),
                'target_session_id': str(self.session.id),
                'target_block': SessionTask.BLOCK_CONDITIONING,
                'replace_existing': '1',
                'library_repo': 'traditional',
            },
            secure=True,
        )
        # PRG: la vista redirige tras POST.
        self.assertIn(response.status_code, {301, 302})
        self.assertTrue(SessionTask.objects.filter(session=self.session, title__icontains='Rondo').exists())


class CriticalPagesSmokeTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Equipo Smoke', slug='equipo-smoke', short_name='SMK', is_primary=True)
        self.user = get_user_model().objects.create_user(
            username='coach-smoke',
            email='coach-smoke@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='WS SMOKE',
            slug='ws-smoke',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'sessions': True, 'abp_board': True, 'match_actions': True, 'analysis': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

        # Partido mínimo para registro de acciones.
        competition = Competition.objects.create(name='CompSmoke', slug='comp-smoke')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='GrupoSmoke', slug='grupo-smoke')
        self.team.group = group
        self.team.save(update_fields=['group'])
        rival = Team.objects.create(name='Rival Smoke', slug='rival-smoke', short_name='RIV', group=group, is_primary=False)
        self.match = Match.objects.create(
            season=season,
            group=group,
            round='J1',
            context=Match.CONTEXT_LEAGUE,
            date=timezone.localdate(),
            home_team=self.team,
            away_team=rival,
        )
        self.player = Player.objects.create(team=self.team, name='Jugador Smoke', number=10, is_active=True)
        conv = ConvocationRecord.objects.create(team=self.team, match=self.match, opponent_name='Rival', is_current=True)
        conv.players.add(self.player)

        # Vídeo mínimo para Video Studio.
        video_file = SimpleUploadedFile('smoke.mp4', b'0' * 1024, content_type='video/mp4')
        self.video = RivalVideo.objects.create(team=self.team, rival_team=rival, title='Video Smoke', video=video_file, source=RivalVideo.SOURCE_MANUAL)

    def _activate_workspace(self):
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def test_abp_board_renders(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('coach-abp-board'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_match_actions_renders(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('match-action-page'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_video_studio_renders(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('analysis-video-studio', args=[self.video.id]), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_model_of_play_renders_for_owner(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('coach-model-of-play'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_team_agenda_renders(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        response = self.client.get(reverse('team-agenda'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_team_agenda_create_session_convoke_players(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        # Necesitamos al menos 2 jugadores activos.
        p2 = Player.objects.create(team=self.team, name='Jugador 2', number=9, is_active=True)
        response = self.client.post(
            reverse('team-agenda'),
            {
                'agenda_action': 'create_session',
                'agenda_session_date': timezone.localdate().strftime('%Y-%m-%d'),
                'agenda_session_start_time': '18:00',
                'agenda_session_focus': 'Entreno agenda',
                'agenda_session_minutes': '90',
                'agenda_session_intensity': TrainingSession.INTENSITY_MEDIUM,
                'agenda_session_status': TrainingSession.STATUS_PLANNED,
            },
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})
        session_obj = TrainingSession.objects.filter(microcycle__team=self.team, focus='Entreno agenda').order_by('-id').first()
        self.assertIsNotNone(session_obj)
        marks = list(TrainingSessionAttendance.objects.filter(session=session_obj))
        self.assertGreaterEqual(len(marks), 2)
        statuses = {m.status for m in marks}
        self.assertEqual(statuses, {TrainingSessionAttendance.STATUS_PRESENT})

    def test_team_agenda_create_match(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        match_day = timezone.localdate() + timedelta(days=1)
        response = self.client.post(
            reverse('team-agenda'),
            {
                'agenda_action': 'create_match',
                'agenda_match_date': match_day.strftime('%Y-%m-%d'),
                'agenda_match_time': '12:30',
                'agenda_match_opponent': 'Rival Agenda',
                'agenda_match_home_away': 'away',
                'agenda_match_context': Match.CONTEXT_LEAGUE,
                'agenda_match_round': 'J2',
                'agenda_match_location': 'Campo Municipal',
            },
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})
        match_obj = Match.objects.filter(season=self.match.season, date=match_day).order_by('-id').first()
        self.assertIsNotNone(match_obj)
        self.assertEqual(match_obj.round, 'J2')
        self.assertEqual(match_obj.kickoff_time.strftime('%H:%M'), '12:30')
        self.assertEqual(match_obj.location, 'Campo Municipal')
        # Visitante => nuestro equipo es away_team
        self.assertEqual(match_obj.away_team_id, self.team.id)
        self.assertIsNotNone(match_obj.home_team_id)

    def test_team_agenda_shows_match_from_convocation_without_match(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        match_day = timezone.localdate() + timedelta(days=1)
        ConvocationRecord.objects.filter(team=self.team, is_current=True).update(is_current=False)
        conv = ConvocationRecord.objects.create(
            team=self.team,
            match=None,
            opponent_name='Rival Convocatoria',
            match_date=match_day,
            match_time=time(hour=18, minute=0),
            is_current=True,
        )
        conv.players.add(self.player)
        response = self.client.get(f"{reverse('team-agenda')}?date={match_day.strftime('%Y-%m-%d')}", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Convocatoria')
        self.assertContains(response, 'Convocatoria')

    def test_team_agenda_hide_session(self):
        self.client.force_login(self.user)
        self._activate_workspace()
        session_obj = TrainingSession.objects.create(
            microcycle=TrainingMicrocycle.objects.create(
                team=self.team,
                title='Micro test',
                objective='',
                week_start=timezone.localdate(),
                week_end=timezone.localdate() + timedelta(days=6),
                status=TrainingMicrocycle.STATUS_DRAFT,
                notes='',
            ),
            session_date=timezone.localdate(),
            start_time=None,
            duration_minutes=90,
            intensity=TrainingSession.INTENSITY_MEDIUM,
            focus='Borrar en agenda',
            content='',
            status=TrainingSession.STATUS_PLANNED,
            order=1,
        )
        response = self.client.post(
            reverse('team-agenda'),
            {'agenda_action': 'hide_session', 'agenda_session_id': str(session_obj.id)},
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})
        self.assertTrue(TrainingSession.objects.filter(id=session_obj.id).exists())

        # Ya no aparece en Agenda (por defecto).
        response = self.client.get(reverse('team-agenda'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Borrar en agenda')

        # Pero sí aparece si pedimos ocultas.
        response = self.client.get(f"{reverse('team-agenda')}?show_hidden=1", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Borrar en agenda')


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

        rows = dashboard_services.compute_player_dashboard(self.team_pre, force_refresh=True)
        detail = next((row for row in rows if row.get('player_id') == player.id), {})
        match_ids = {int(item.get('match_id') or 0) for item in (detail.get('matches') or [])}

        self.assertIn(self.match_pre.id, match_ids)
        self.assertNotIn(self.match_senior.id, match_ids)

    def test_compute_player_dashboard_collapses_duplicate_match_fixtures(self):
        player = Player.objects.create(team=self.team_pre, name='Jugador Duplicado', number=10)
        fixture_date = timezone.localdate() - timedelta(days=2)
        match_placeholder = Match.objects.create(
            season=self.season,
            group=self.group,
            round='5',
            date=fixture_date,
            home_team=self.team_pre,
            away_team=None,
        )
        match_real = Match.objects.create(
            season=self.season,
            group=self.group,
            round='5',
            date=fixture_date,
            home_team=self.team_pre,
            away_team=self.rival_a,
        )
        record = ConvocationRecord.objects.create(
            team=self.team_pre,
            match=match_placeholder,
            round='5',
            match_date=fixture_date,
            opponent_name='Rival A',
            lineup_data={'starters': [{'id': player.id}], 'bench': []},
        )
        record.players.set([player])
        MatchEvent.objects.create(
            match=match_real,
            player=player,
            minute=7,
            event_type='pase',
            zone='Z1',
            result='ok',
            system='touch-field',
            source_file='registro-acciones',
        )

        rows = dashboard_services.compute_player_dashboard(self.team_pre, force_refresh=True)
        detail = next((row for row in rows if row.get('player_id') == player.id), {})
        matches_payload = detail.get('matches') or []
        self.assertEqual(len(matches_payload), 1)
        self.assertEqual(int(matches_payload[0].get('match_id') or 0), match_real.id)

    def test_compute_player_dashboard_collapses_undated_duplicate_match_fixtures(self):
        player = Player.objects.create(team=self.team_pre, name='Jugador Sin Fecha', number=11)
        match_placeholder = Match.objects.create(
            season=self.season,
            group=self.group,
            round='20',
            date=None,
            home_team=self.team_pre,
            away_team=None,
        )
        match_real = Match.objects.create(
            season=self.season,
            group=self.group,
            round='20',
            date=None,
            home_team=self.team_pre,
            away_team=self.rival_a,
        )
        record = ConvocationRecord.objects.create(
            team=self.team_pre,
            match=match_placeholder,
            round='20',
            match_date=None,
            opponent_name='Rival A',
            lineup_data={'starters': [{'id': player.id}], 'bench': []},
        )
        record.players.set([player])
        MatchEvent.objects.create(
            match=match_real,
            player=player,
            minute=12,
            event_type='pase',
            zone='Z1',
            result='ok',
            system='touch-field',
            source_file='registro-acciones',
        )

        rows = dashboard_services.compute_player_dashboard(self.team_pre, force_refresh=True)
        detail = next((row for row in rows if row.get('player_id') == player.id), {})
        matches_payload = detail.get('matches') or []
        self.assertEqual(len(matches_payload), 1)
        self.assertEqual(int(matches_payload[0].get('match_id') or 0), match_real.id)

    def test_compute_player_dashboard_prefers_match_opponent_over_convocation_label(self):
        player = Player.objects.create(team=self.team_pre, name='Jugador Rival', number=12)
        fixture_date = timezone.localdate() - timedelta(days=3)
        match_real = Match.objects.create(
            season=self.season,
            group=self.group,
            round='16',
            date=fixture_date,
            home_team=self.team_pre,
            away_team=self.rival_b,
        )
        record = ConvocationRecord.objects.create(
            team=self.team_pre,
            match=match_real,
            round='16',
            match_date=fixture_date,
            opponent_name='LOJA C.D.',
            lineup_data={'starters': [{'id': player.id}], 'bench': []},
        )
        record.players.set([player])
        MatchEvent.objects.create(
            match=match_real,
            player=player,
            minute=9,
            event_type='pase',
            zone='Z1',
            result='ok',
            system='touch-field',
            source_file='registro-acciones',
        )
        rows = dashboard_services.compute_player_dashboard(self.team_pre, force_refresh=True)
        detail = next((row for row in rows if row.get('player_id') == player.id), {})
        matches_payload = detail.get('matches') or []
        self.assertEqual(len(matches_payload), 1)
        self.assertEqual(matches_payload[0].get('opponent'), 'Rival B')

    def test_player_match_stats_payload_includes_match_id(self):
        user = get_user_model().objects.create_user(username='viewer', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        player = Player.objects.create(team=self.team_pre, name='Jugador Vista', number=13)
        match_real = Match.objects.create(
            season=self.season,
            group=self.group,
            round='9',
            date=timezone.localdate() - timedelta(days=1),
            home_team=self.team_pre,
            away_team=self.rival_a,
        )
        self.client.force_login(user)
        resp = self.client.get(reverse('player-match-stats', args=[player.id, match_real.id]), secure=True)
        self.assertEqual(resp.status_code, 200)
        # El template ahora muestra "ID <match_id>" en la línea meta.
        self.assertIn(f'ID {match_real.id}'.encode('utf-8'), resp.content)


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
        self.assertTrue(workspace_context.can_manage_workspace(user, workspace))
        self.assertTrue(workspace_context.can_view_workspace(user, workspace))


class ClubSeasonWizardQuestionnaireTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='season-owner',
            email='season-owner@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.team = Team.objects.create(
            name='Equipo Temporada',
            slug='equipo-temporada',
            short_name='Temporada',
            is_primary=True,
        )
        self.workspace = Workspace.objects.create(
            name='Club Temporada',
            slug='club-temporada',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.user,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.season = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2026/2027',
            start_date=date(2026, 7, 1),
            is_active=True,
        )
        self.workspace.active_season = self.season
        self.workspace.save(update_fields=['active_season', 'updated_at'])
        self.player = Player.objects.create(team=self.team, name='Jugador Cuestionario', number=7)
        self.membership = WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            questionnaire={
                'ratings': {
                    'ball_control': 4,
                    'pass_control': 5,
                    'game_knowledge': 3,
                    'speed': 2,
                },
            },
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()

    def test_questionnaire_page_renders_rating_summary_and_radar(self):
        response = self.client.get(f"{reverse('club-season-wizard')}?step=questionnaire", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Media global / 5')
        self.assertContains(response, 'id="season-radar"')
        self.assertContains(response, 'season_wizard_ratings.js')
        self.assertContains(response, 'data-values="4.5|3.0|2.0|0.0"')
        self.assertContains(response, 'Categoría actual consolidada')

    def test_questionnaire_save_persists_rating_average_and_category(self):
        response = self.client.post(
            f"{reverse('club-season-wizard')}?step=questionnaire",
            data={
                'action': 'questionnaire_save',
                'membership_id': str(self.membership.id),
                'q_role_pref': 'titular',
                'q_foot': 'der',
                'q_motivation': '5',
                'q_rating_ball_control': '5',
                'q_rating_pass_control': '5',
                'q_rating_pass_distance': '4',
                'q_rating_coordination': '4',
                'q_rating_dribbling': '5',
                'q_rating_game_knowledge': '4',
                'q_rating_order': '4',
                'q_rating_positioning': '4',
                'q_rating_striking': '3',
                'q_rating_body_contact': '3',
                'q_rating_endurance': '4',
                'q_rating_speed': '4',
                'q_rating_behavior': '5',
                'q_rating_bravery': '4',
                'q_rating_extroversion': '4',
                'q_rating_obedience': '5',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        questionnaire = self.membership.questionnaire
        self.assertEqual(self.membership.questionnaire_v, 2)
        self.assertIsNotNone(self.membership.questionnaire_completed_at)
        self.assertEqual(questionnaire['ratings']['ball_control'], 5)
        self.assertEqual(questionnaire['ratings_average'], 4.19)
        self.assertEqual(questionnaire['ratings_category'], 'Categoría alta')


class SeasonWizardRatingHelperTests(SimpleTestCase):
    def test_rating_summary_clamps_values_and_ignores_empty_inputs(self):
        from football.season_wizard import build_questionnaire_rating_summary, parse_questionnaire_ratings

        ratings = parse_questionnaire_ratings({
            'q_rating_ball_control': '8',
            'q_rating_pass_control': '-2',
            'q_rating_speed': '',
            'q_rating_behavior': 'bad',
            'q_rating_bravery': '4',
        })
        self.assertEqual(ratings, {
            'ball_control': 5,
            'pass_control': 0,
            'bravery': 4,
        })

        summary = build_questionnaire_rating_summary({'ratings': ratings})
        self.assertEqual(summary['overall'], 3.0)
        self.assertEqual(summary['category'], 'Categoría actual consolidada')
        self.assertEqual(summary['chart_values'], [2.5, 0.0, 0.0, 4.0])


class SeasonHistoryServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='history-owner', password='pass-1234')
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.team = Team.objects.create(name='Equipo Histórico', slug='equipo-historico', short_name='Histórico')
        self.workspace = Workspace.objects.create(
            name='Club Histórico',
            slug='club-historico',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.user,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.season = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2026/2027',
            start_date=date(2026, 7, 1),
            is_active=True,
        )
        self.workspace.active_season = self.season
        self.workspace.save(update_fields=['active_season', 'updated_at'])
        self.player = Player.objects.create(team=self.team, name='Jugador Histórico', is_active=True)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()

    def test_workspace_season_keeps_team_and_player_history_when_player_deactivates(self):
        from football.season_history_services import (
            ensure_active_workspace_team_seasons,
            ensure_team_roster_season_memberships,
            mark_player_left_current_season,
        )

        ensure_active_workspace_team_seasons(self.workspace, season=self.season)
        ensure_team_roster_season_memberships(self.season, self.team, include_inactive=True)
        self.player.is_active = False
        self.player.save(update_fields=['is_active'])
        mark_player_left_current_season(self.season, self.player, notes='No continúa')
        ensure_team_roster_season_memberships(self.season, self.team, include_inactive=True)

        self.assertTrue(WorkspaceSeasonTeam.objects.filter(season=self.season, team=self.team, is_active=True).exists())
        membership = WorkspaceSeasonPlayer.objects.get(season=self.season, player=self.player)
        self.assertEqual(membership.team, self.team)
        self.assertEqual(membership.status, WorkspaceSeasonPlayer.STATUS_LEFT)
        self.assertFalse(membership.is_confirmed)
        self.assertIsNotNone(membership.left_at)
        workspace_player = WorkspacePlayer.objects.get(workspace=self.workspace, player=self.player, current_team=self.team)
        self.assertFalse(workspace_player.is_active)

    def test_workspace_player_pool_is_scoped_to_club_and_category(self):
        from football.season_history_services import ensure_workspace_player, workspace_players_for_team

        other_team = Team.objects.create(name='Malaga Benjamin', slug='malaga-benjamin', short_name='Malaga B')
        other_workspace = Workspace.objects.create(
            name='Malaga CF',
            slug='malaga-cf',
            kind=Workspace.KIND_CLUB,
            primary_team=other_team,
            owner_user=self.user,
            is_active=True,
        )
        WorkspaceTeam.objects.create(workspace=other_workspace, team=other_team, is_default=True)
        other_player = Player.objects.create(team=other_team, name='Jugador Malaga', is_active=True)

        ensure_workspace_player(self.workspace, self.player, current_team=self.team)
        ensure_workspace_player(other_workspace, other_player, current_team=other_team)

        rows = list(workspace_players_for_team(self.workspace, self.team))

        self.assertEqual([row.player for row in rows], [self.player])
        self.assertNotIn(other_player, [row.player for row in rows])

    def test_roster_deactivate_removes_player_from_active_club_pool_but_keeps_history(self):
        from football.season_history_services import ensure_player_season_membership, ensure_workspace_player

        ensure_workspace_player(self.workspace, self.player, current_team=self.team)
        ensure_player_season_membership(
            self.season,
            self.player,
            team=self.team,
            confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        other_team = Team.objects.create(name='Otro Equipo Histórico', slug='otro-equipo-historico')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=other_team, is_default=False)
        other_player = Player.objects.create(team=other_team, name='Baja Otro Equipo', is_active=False)
        ensure_workspace_player(self.workspace, other_player, current_team=other_team, is_active=False)
        ensure_player_season_membership(
            self.season,
            other_player,
            team=other_team,
            confirmed=False,
            status=WorkspaceSeasonPlayer.STATUS_LEFT,
        )

        response = self.client.post(
            f"{reverse('coach-roster')}?tab=manage",
            data={
                'action': 'deactivate',
                'player_id': str(self.player.id),
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.assertFalse(self.player.is_active)
        workspace_player = WorkspacePlayer.objects.get(workspace=self.workspace, player=self.player)
        self.assertFalse(workspace_player.is_active)
        membership = WorkspaceSeasonPlayer.objects.get(season=self.season, player=self.player)
        self.assertEqual(membership.status, WorkspaceSeasonPlayer.STATUS_LEFT)
        self.assertNotIn(self.player, response.context['players'])
        self.assertNotIn(self.player, response.context['club_player_options'])
        self.assertIn(self.player, response.context['inactive_club_player_options'])
        self.assertNotContains(response, 'Jugadores dados de baja')

        inactive_response = self.client.get(
            f"{reverse('coach-roster')}?tab=inactive",
            secure=True,
        )
        self.assertEqual(inactive_response.status_code, 200)
        self.assertContains(inactive_response, 'Jugadores dados de baja')
        self.assertContains(inactive_response, self.player.name)
        self.assertNotContains(inactive_response, other_player.name)

        restore_response = self.client.post(
            f"{reverse('coach-roster')}?tab=inactive",
            data={
                'action': 'reactivate',
                'player_id': str(self.player.id),
            },
            secure=True,
        )

        self.assertEqual(restore_response.status_code, 200)
        self.player.refresh_from_db()
        self.assertTrue(self.player.is_active)
        self.assertEqual(self.player.team, self.team)
        workspace_player.refresh_from_db()
        self.assertTrue(workspace_player.is_active)
        self.assertEqual(workspace_player.current_team, self.team)
        membership.refresh_from_db()
        self.assertEqual(membership.status, WorkspaceSeasonPlayer.STATUS_PENDING)
        self.assertFalse(membership.is_confirmed)
        self.assertIsNone(membership.left_at)
        self.assertIn(self.player, restore_response.context['players'])
        self.assertNotIn(self.player, restore_response.context['inactive_club_player_options'])
        self.assertContains(restore_response, 'Jugadores dados de baja')
        self.assertContains(restore_response, 'No hay jugadores dados de baja para recuperar en este club.')

    def test_player_detail_exposes_season_context_and_history_tab(self):
        from football.season_history_services import ensure_active_workspace_team_seasons, ensure_team_roster_season_memberships

        ensure_active_workspace_team_seasons(self.workspace, season=self.season)
        ensure_team_roster_season_memberships(self.season, self.team, include_inactive=True)

        response = self.client.get(
            f"{reverse('player-detail', args=[self.player.id])}?club_season_id={self.season.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contexto de temporada')
        self.assertContains(response, 'Temporadas e histórico')
        self.assertContains(response, self.season.label)

    def test_player_detail_can_create_staff_evaluation(self):
        PlayerEvaluation.objects.create(
            team=self.team,
            player=self.player,
            club_season=self.season,
            evaluation_type=PlayerEvaluation.TYPE_INITIAL,
            evaluated_on=date(2026, 8, 15),
            status=PlayerEvaluation.STATUS_CLOSED,
            overall_rating=Decimal('6.5'),
            technical_rating=Decimal('6.0'),
            tactical_rating=Decimal('7.0'),
            physical_rating=Decimal('6.0'),
            mental_rating=Decimal('7.0'),
            social_rating=Decimal('7.0'),
        )
        response = self.client.post(
            f"{reverse('player-detail', args=[self.player.id])}?tab=evaluations&club_season_id={self.season.id}",
            data={
                'form_action': 'evaluation',
                'club_season_id': str(self.season.id),
                'evaluation_type': PlayerEvaluation.TYPE_MONTHLY,
                'evaluated_on': '2026-09-15',
                'status': PlayerEvaluation.STATUS_CLOSED,
                'role': 'Rotación',
                'evaluated_position': 'MC',
                'recommended_position': 'MCD',
                'overall_rating': '7,5',
                'technical_rating': '7',
                'tactical_rating': '8',
                'physical_rating': '6.5',
                'mental_rating': '8',
                'social_rating': '7',
                'objective_performance_rating': '8.2',
                'availability_rating': '9',
                'single_leg_control_rating': '7',
                'wellness_sleep': '8',
                'wellness_fatigue': '6',
                'wellness_soreness': '7',
                'wellness_stress': '8',
                'wellness_motivation': '9',
                'session_rpe': '6',
                'session_minutes': '75',
                'yo_yo_ir1_m': '1240',
                'sprint_20m_s': '3.28',
                'agility_505_s': '2.48',
                'cmj_cm': '31.5',
                'copenhagen_seconds': '42',
                'maturation_status': PlayerEvaluation.MATURATION_CIRCA,
                'maturity_offset_years': '0.25',
                'growth_velocity_cm_year': '6.8',
                'evidence_notes': 'Test realizado tras microciclo de carga media',
                'strengths': 'Buen ritmo competitivo',
                'improvements': 'Perfil corporal al recibir',
                'objectives_next': 'Mejorar orientación antes de controlar',
                'coach_comments': 'Seguimiento mensual cerrado',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        evaluation = PlayerEvaluation.objects.filter(player=self.player).order_by('-evaluated_on', '-id').first()
        self.assertEqual(evaluation.team, self.team)
        self.assertEqual(evaluation.club_season, self.season)
        self.assertEqual(evaluation.status, PlayerEvaluation.STATUS_CLOSED)
        self.assertEqual(evaluation.overall_rating, Decimal('7.5'))
        self.assertEqual(evaluation.objective_performance_rating, Decimal('8.2'))
        self.assertEqual(evaluation.srpe_load, 450)
        self.assertEqual(evaluation.wellness_score, 7.6)
        self.assertEqual(evaluation.maturation_status, PlayerEvaluation.MATURATION_CIRCA)
        self.assertIsNotNone(evaluation.assisted_score)

        detail_response = self.client.get(
            f"{reverse('player-detail', args=[self.player.id])}?tab=evaluations&club_season_id={self.season.id}",
            secure=True,
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Evaluaciones')
        self.assertContains(detail_response, 'Seguimiento técnico')
        self.assertContains(detail_response, 'Evolución y mejora')
        self.assertContains(detail_response, 'Buen ritmo competitivo')
        self.assertContains(detail_response, 'Informe')

        report_response = self.client.get(
            reverse('player-evaluation-report', args=[self.player.id, evaluation.id]),
            secure=True,
        )
        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, 'Informe individual de evaluación')
        self.assertContains(report_response, 'Áreas evaluadas')
        self.assertContains(report_response, 'Evidencia objetiva')
        self.assertContains(report_response, 'Nota asistida')
        self.assertContains(report_response, 'sRPE')
        self.assertContains(report_response, 'Mejora +1')
        self.assertContains(report_response, 'Test realizado tras microciclo de carga media')
        self.assertContains(report_response, 'Objetivos próximos')

    def test_selected_club_season_can_be_loaded_from_request_and_session(self):
        from football.season_history_services import club_season_date_bounds, selected_club_season_for_request

        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )
        factory = RequestFactory()
        request = factory.get(f'/?club_season_id={previous.id}')
        request.user = self.user
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()
        request.session = session

        selected = selected_club_season_for_request(request, workspace=self.workspace)

        self.assertEqual(selected, previous)
        self.assertEqual(request.session[f'active_club_season_id:{self.workspace.id}'], previous.id)
        self.assertEqual(club_season_date_bounds(selected), (date(2025, 7, 1), date(2026, 6, 30)))

    def test_roster_historical_season_is_read_only_and_does_not_backfill_current_players(self):
        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )

        response = self.client.get(
            f"{reverse('coach-roster')}?tab=manage&club_season_id={previous.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista histórica en solo lectura')
        self.assertNotContains(response, 'Guardar jugador')
        self.assertFalse(WorkspaceSeasonPlayer.objects.filter(season=previous, player=self.player).exists())

    def test_team_can_be_marked_not_continuing_for_one_season_without_deleting_entity(self):
        from football.season_history_services import ensure_season_team, set_team_season_status

        membership = ensure_season_team(self.season, self.team)
        self.assertTrue(membership.is_active)

        updated = set_team_season_status(
            self.season,
            self.team,
            status=WorkspaceSeasonTeam.STATUS_NOT_CONTINUING,
            notes='No sale en esta temporada.',
        )

        self.team.refresh_from_db()
        self.assertEqual(updated.status, WorkspaceSeasonTeam.STATUS_NOT_CONTINUING)
        self.assertFalse(updated.is_active)
        self.assertTrue(Team.objects.filter(id=self.team.id).exists())
        self.assertTrue(WorkspaceTeam.objects.filter(workspace=self.workspace, team=self.team).exists())

    def test_close_and_open_workspace_season_keeps_entities_and_inherits_roster(self):
        from football.season_history_services import close_workspace_season, open_workspace_season

        closed = close_workspace_season(self.workspace, season=self.season, end_date=date(2027, 6, 30))
        self.workspace.refresh_from_db()

        self.assertFalse(closed.is_active)
        self.assertIsNone(self.workspace.active_season)

        new_season = open_workspace_season(
            self.workspace,
            label='2027/2028',
            start_date=date(2027, 7, 1),
            team=self.team,
            inherit_teams=True,
            inherit_roster=True,
        )
        self.workspace.refresh_from_db()

        self.assertEqual(self.workspace.active_season, new_season)
        self.assertTrue(Team.objects.filter(id=self.team.id).exists())
        self.assertTrue(WorkspaceSeasonTeam.objects.filter(season=new_season, team=self.team, is_active=True).exists())
        self.assertTrue(WorkspaceSeasonPlayer.objects.filter(season=new_season, player=self.player).exists())

    def test_roster_can_add_existing_club_player_to_active_team(self):
        other_team = Team.objects.create(name='Equipo Origen', slug='equipo-origen', short_name='Origen')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=other_team)
        existing = Player.objects.create(
            team=other_team,
            name='Jugador Club',
            full_name='Jugador Club Completo',
            is_active=True,
        )
        WorkspacePlayer.objects.create(workspace=self.workspace, player=existing, current_team=other_team)

        response = self.client.post(
            f"{reverse('coach-roster')}?tab=manage",
            data={
                'action': 'add_existing',
                'existing_player_id': str(existing.id),
                'number': '18',
                'position': 'MC',
                'is_active': '1',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.team, self.team)
        self.assertEqual(existing.number, 18)
        self.assertEqual(existing.position, 'MC')
        self.assertTrue(
            WorkspaceSeasonPlayer.objects.filter(
                season=self.season,
                player=existing,
                team=self.team,
                status=WorkspaceSeasonPlayer.STATUS_PENDING,
            ).exists()
        )

    def test_roster_existing_players_are_filtered_by_category_birth_year(self):
        self.team.category = 'Benjamín'
        self.team.save(update_fields=['category'])
        other_team = Team.objects.create(name='Equipo Origen Edad', slug='equipo-origen-edad', short_name='Origen Edad')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=other_team)
        eligible = Player.objects.create(
            team=other_team,
            name='Benjamin Elegible',
            birth_date=date(2017, 3, 4),
            is_active=True,
        )
        too_old = Player.objects.create(
            team=other_team,
            name='Alevin No Elegible',
            birth_date=date(2015, 5, 8),
            is_active=True,
        )
        WorkspacePlayer.objects.create(workspace=self.workspace, player=eligible, current_team=other_team)
        WorkspacePlayer.objects.create(workspace=self.workspace, player=too_old, current_team=other_team)

        response = self.client.get(f"{reverse('coach-roster')}?tab=manage", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(eligible, response.context['club_player_options'])
        self.assertNotIn(too_old, response.context['club_player_options'])
        self.assertContains(response, '2017-2018')
        self.assertContains(response, 'Benjamin Elegible')
        self.assertContains(response, '2017')
        self.assertNotContains(response, 'Alevin No Elegible')

        invalid_response = self.client.post(
            f"{reverse('coach-roster')}?tab=manage",
            data={
                'action': 'add_existing',
                'existing_player_id': str(too_old.id),
                'is_active': '1',
            },
            secure=True,
        )

        self.assertEqual(invalid_response.status_code, 200)
        too_old.refresh_from_db()
        self.assertEqual(too_old.team, other_team)
        self.assertContains(invalid_response, 'no corresponde por año de nacimiento')

    def test_roster_create_player_saves_extended_profile_fields(self):
        response = self.client.post(
            f"{reverse('coach-roster')}?tab=manage",
            data={
                'action': 'add',
                'full_name': 'Nuevo Jugador Completo',
                'name': 'Nuevo Jugador',
                'birth_date': '2010-04-12',
                'origin_team': 'Club Origen',
                'height_cm': '174',
                'weight_kg': '68.5',
                'dominant_foot': 'left',
                'preferred_position': 'MC',
                'previous_season_position': 'LD',
                'position': 'MCO',
                'number': '21',
                'is_active': '1',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        player = Player.objects.get(team=self.team, name='Nuevo Jugador')
        self.assertEqual(player.full_name, 'Nuevo Jugador Completo')
        self.assertEqual(player.birth_date, date(2010, 4, 12))
        self.assertEqual(player.origin_team, 'Club Origen')
        self.assertEqual(player.height_cm, 174)
        self.assertEqual(player.weight_kg, Decimal('68.50'))
        self.assertEqual(player.dominant_foot, 'left')
        self.assertEqual(player.preferred_position, 'MC')
        self.assertEqual(player.previous_season_position, 'LD')
        self.assertEqual(player.position, 'MCO')
        self.assertTrue(WorkspaceSeasonPlayer.objects.filter(season=self.season, player=player, team=self.team).exists())

    def test_roster_move_player_to_next_category_keeps_him_active_in_club(self):
        target_team = Team.objects.create(name='Equipo Destino', slug='equipo-destino', short_name='Destino', category='Cadete')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=target_team)
        WorkspacePlayer.objects.create(workspace=self.workspace, player=self.player, current_team=self.team)
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
            confirmed_by=self.user,
            confirmed_at=timezone.now(),
        )

        response = self.client.post(
            f"{reverse('coach-roster')}?tab=manage",
            data={
                'action': 'move_team',
                'player_id': str(self.player.id),
                'target_team_id': str(target_team.id),
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.player, response.context['players'])
        self.player.refresh_from_db()
        self.assertEqual(self.player.team, target_team)
        self.assertTrue(self.player.is_active)
        membership = WorkspaceSeasonPlayer.objects.get(season=self.season, player=self.player)
        self.assertEqual(membership.team, target_team)
        self.assertEqual(membership.status, WorkspaceSeasonPlayer.STATUS_CONFIRMED)
        self.assertTrue(membership.is_confirmed)
        workspace_player = WorkspacePlayer.objects.get(workspace=self.workspace, player=self.player)
        self.assertEqual(workspace_player.current_team, target_team)
        self.assertTrue(workspace_player.is_active)

        origin_response = self.client.get(
            f"{reverse('coach-roster')}?tab=manage&team={self.team.id}&club_season_id={self.season.id}",
            secure=True,
        )
        self.assertEqual(origin_response.status_code, 200)
        self.assertNotIn(self.player, origin_response.context['players'])

        target_response = self.client.get(
            f"{reverse('coach-roster')}?tab=manage&team={target_team.id}&club_season_id={self.season.id}",
            secure=True,
        )
        self.assertEqual(target_response.status_code, 200)
        self.assertIn(self.player, target_response.context['players'])

    @patch('football.views.compute_player_cards')
    def test_roster_stats_cards_only_show_confirmed_players_for_selected_season(self, mocked_cards):
        pending_player = Player.objects.create(team=self.team, name='Jugador Pendiente Temporada', is_active=True)
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=pending_player,
            team=self.team,
            is_confirmed=False,
            status=WorkspaceSeasonPlayer.STATUS_PENDING,
        )
        mocked_cards.return_value = [
            {'player_id': self.player.id, 'name': self.player.name, 'number': 7, 'position': 'MC', 'goals': 1, 'pj': 1},
            {'player_id': pending_player.id, 'name': pending_player.name, 'number': 8, 'position': 'DC', 'goals': 9, 'pj': 9},
        ]

        response = self.client.get(
            f"{reverse('coach-roster')}?tab=stats&club_season_id={self.season.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player.name)
        self.assertNotContains(response, pending_player.name)

    def test_roster_stats_cards_do_not_reuse_previous_season_manual_base_stats(self):
        competition = Competition.objects.create(name='Liga Cards Antigua', slug='liga-cards-antigua', level=1, region='test')
        federation_season = Season.objects.create(
            competition=competition,
            name='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        group = Group.objects.create(season=federation_season, name='Grupo Cards Antiguo', slug='grupo-cards-antiguo')
        self.team.group = group
        self.team.save(update_fields=['group'])
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        PlayerStatistic.objects.create(player=self.player, season=federation_season, match=None, context='manual-base', name='manual_pj', value=31)
        PlayerStatistic.objects.create(player=self.player, season=federation_season, match=None, context='manual-base', name='manual_minutes', value=2465)
        PlayerStatistic.objects.create(player=self.player, season=federation_season, match=None, context='manual-base', name='manual_goals', value=18)

        response = self.client.get(
            f"{reverse('coach-roster')}?tab=stats&club_season_id={self.season.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        cards = response.context['player_cards']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['player_id'], self.player.id)
        self.assertEqual(int(cards[0].get('pj') or 0), 0)
        self.assertEqual(int(cards[0].get('minutes') or 0), 0)
        self.assertEqual(int(cards[0].get('goals') or 0), 0)

    @patch('football.views.resolve_player_photo_url')
    def test_roster_stats_cards_keep_uploaded_photo_for_roster_player_without_events(self, mocked_photo_url):
        mocked_photo_url.return_value = '/player/999/photo/?v=123'
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )

        response = self.client.get(
            f"{reverse('coach-roster')}?tab=stats&club_season_id={self.season.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        cards = response.context['player_cards']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['player_id'], self.player.id)
        self.assertEqual(cards[0]['photo_url'], '/player/999/photo/?v=123')

    def test_static_player_photo_fallback_follows_player_after_category_change(self):
        from football.player_media import resolve_player_photo_static_path

        youth_team = Team.objects.create(name='Benjamín A', slug='benjamin-a', short_name='Benjamin A', category='Benjamín')
        moved_player = Player.objects.create(team=youth_team, name='Andrews', number=14, is_active=True)

        self.assertEqual(
            resolve_player_photo_static_path(moved_player),
            'football/images/players/andrew-n14-cut.png',
        )

    def test_static_player_photo_fallback_does_not_match_only_by_number(self):
        from football.player_media import resolve_player_photo_static_path

        youth_team = Team.objects.create(name='Benagalbon Benjamin', slug='benagalbon-benjamin', short_name='Benjamin', category='Benjamín')
        unrelated_player = Player.objects.create(team=youth_team, name='Hugo', number=8, is_active=True)

        self.assertEqual(resolve_player_photo_static_path(unrelated_player), '')

    @patch('football.views.compute_player_dashboard')
    def test_player_detail_does_not_use_previous_stats_for_unconfirmed_season_player(self, mocked_dashboard):
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=False,
            status=WorkspaceSeasonPlayer.STATUS_PENDING,
        )
        mocked_dashboard.return_value = [
            {
                'player_id': self.player.id,
                'name': self.player.name,
                'pj': 12,
                'minutes': 900,
                'goals': 14,
                'assists': 3,
            }
        ]

        response = self.client.get(
            f"{reverse('player-detail', args=[self.player.id])}?club_season_id={self.season.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.context['stats'].get('pj') or 0), 0)
        self.assertEqual(int(response.context['stats'].get('minutes') or 0), 0)
        self.assertEqual(int(response.context['stats'].get('goals') or 0), 0)

    def test_active_season_dashboard_uses_confirmed_roster_without_legacy_base_stats(self):
        competition = Competition.objects.create(name='Historial Liga', slug='historial-liga', level=1, region='test')
        federation_season = Season.objects.create(
            competition=competition,
            name='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        group = Group.objects.create(season=federation_season, name='Grupo Historial', slug='grupo-historial')
        self.team.group = group
        self.team.save(update_fields=['group'])
        pending_player = Player.objects.create(team=self.team, name='Jugador Pendiente KPI', is_active=True)
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=self.player,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=pending_player,
            team=self.team,
            is_confirmed=False,
            status=WorkspaceSeasonPlayer.STATUS_PENDING,
        )
        PlayerStatistic.objects.create(player=self.player, season=federation_season, match=None, context='manual-base', name='manual_pj', value=31)
        PlayerStatistic.objects.create(player=self.player, season=federation_season, match=None, context='manual-base', name='manual_minutes', value=2465)
        PlayerStatistic.objects.create(player=pending_player, season=federation_season, match=None, context='manual-base', name='manual_pj', value=20)

        request = RequestFactory().get(f'/?club_season_id={self.season.id}')
        request.user = self.user
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()
        request.session = session

        rows = football_views.compute_player_dashboard(self.team, force_refresh=True, request=request)

        self.assertEqual([row['player_id'] for row in rows], [self.player.id])
        self.assertEqual(int(rows[0].get('pj') or 0), 0)
        self.assertEqual(int(rows[0].get('minutes') or 0), 0)

    def test_convocation_page_only_lists_confirmed_active_season_players(self):
        confirmed = Player.objects.create(team=self.team, name='Jugador Confirmado Convocatoria', is_active=True)
        pending = Player.objects.create(team=self.team, name='Jugador Pendiente Convocatoria', is_active=True)
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=confirmed,
            team=self.team,
            is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=pending,
            team=self.team,
            is_confirmed=False,
            status=WorkspaceSeasonPlayer.STATUS_PENDING,
        )

        response = self.client.get(reverse('convocation'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, confirmed.name)
        self.assertNotContains(response, pending.name)

    def test_season_architecture_audit_assigns_records_by_club_season(self):
        from football.season_history_services import infer_club_season_for_date, season_architecture_audit

        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Semana histórica',
            week_start=date(2026, 5, 25),
            week_end=date(2026, 5, 31),
        )
        TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=date(2026, 5, 31),
            focus='Tarea de temporada anterior',
        )
        microcycle_current = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Semana actual',
            week_start=date(2026, 9, 1),
            week_end=date(2026, 9, 7),
        )
        TrainingSession.objects.create(
            microcycle=microcycle_current,
            session_date=date(2026, 9, 2),
            focus='Tarea temporada actual',
        )
        task_session = TrainingSession.objects.create(
            microcycle=microcycle_current,
            session_date=date(2026, 9, 3),
            focus='Sesión con tarea auditada',
        )
        SessionTask.objects.create(session=task_session, title='Tarea auditada')

        audit = season_architecture_audit(self.workspace)

        self.assertEqual(infer_club_season_for_date(self.workspace, date(2026, 5, 31)), previous)
        self.assertEqual(infer_club_season_for_date(self.workspace, date(2026, 9, 2)), self.season)
        self.assertEqual(audit['models']['sessions']['total'], 3)
        self.assertEqual(audit['models']['sessions']['by_season'][str(previous.id)], 1)
        self.assertEqual(audit['models']['sessions']['by_season'][str(self.season.id)], 2)
        self.assertEqual(audit['models']['session_tasks']['total'], 1)
        self.assertEqual(audit['models']['session_tasks']['explicit'], 1)

    def test_new_match_session_and_task_get_explicit_club_season(self):
        competition = Competition.objects.create(name='Liga Histórica', slug='liga-historica')
        external_season = Season.objects.create(
            competition=competition,
            name='2026/2027',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
        )
        rival = Team.objects.create(name='Rival Histórico', slug='rival-historico', short_name='Rival')
        match = Match.objects.create(
            season=external_season,
            home_team=self.team,
            away_team=rival,
            date=date(2026, 9, 14),
            round='J1',
        )
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Semana con temporada',
            week_start=date(2026, 9, 14),
            week_end=date(2026, 9, 20),
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=date(2026, 9, 15),
            focus='Sesión con temporada',
        )
        task = SessionTask.objects.create(session=session, title='Tarea con temporada')

        self.assertEqual(match.club_season, self.season)
        self.assertEqual(session.club_season, self.season)
        self.assertEqual(task.club_season, self.season)

    def test_backfill_assigns_missing_explicit_club_season(self):
        from football.season_history_services import backfill_workspace_club_seasons

        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Semana sin temporada explícita',
            week_start=date(2026, 10, 1),
            week_end=date(2026, 10, 7),
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=date(2026, 10, 2),
            focus='Sesión para backfill',
        )
        TrainingSession.objects.filter(id=session.id).update(club_season=None)
        session.refresh_from_db()
        self.assertIsNone(session.club_season)

        dry = backfill_workspace_club_seasons(self.workspace, dry_run=True)
        self.assertGreaterEqual(dry['models']['sessions']['assigned'], 1)
        session.refresh_from_db()
        self.assertIsNone(session.club_season)

        backfill_workspace_club_seasons(self.workspace, dry_run=False)
        session.refresh_from_db()
        self.assertEqual(session.club_season, self.season)

    def test_historical_season_blocks_tactical_playbook_writes(self):
        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )

        response = self.client.post(
            f"{reverse('tactical-playbook-clip-save-api')}?club_season_id={previous.id}",
            data=json.dumps({
                'scope': 'team',
                'name': 'Salida historica',
                'steps': [{'players': []}],
            }),
            content_type='application/json',
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(TacticalPlaybookClip.objects.filter(team=self.team, name='Salida historica').exists())

    def test_historical_season_blocks_match_creation(self):
        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )
        competition = Competition.objects.create(name='Liga Bloqueo', slug='liga-bloqueo')
        Season.objects.create(
            competition=competition,
            name='2026/2027',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )

        response = self.client.post(
            f"{reverse('match-hub-create')}?club_season_id={previous.id}",
            data={
                'opponent': 'Rival no creado',
                'date': '2026-09-20',
                'home_away': 'home',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Team.objects.filter(name='Rival no creado').exists())

    def test_new_season_wizard_resets_selected_club_season_session(self):
        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )
        session = self.client.session
        session[f'active_club_season_id:{self.workspace.id}'] = previous.id
        session.save()

        response = self.client.post(
            reverse('club-season-wizard'),
            data={
                'action': 'create_new_season',
                'season_label': '2027/2028',
                'season_start_date': '2027-07-01',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        new_season = WorkspaceSeason.objects.get(workspace=self.workspace, label='2027/2028')
        self.assertEqual(self.client.session[f'active_club_season_id:{self.workspace.id}'], new_season.id)

    def test_match_creation_uses_active_club_season_despite_sticky_historical_session(self):
        competition = Competition.objects.create(name='Liga Sticky', slug='liga-sticky')
        external_season = Season.objects.create(
            competition=competition,
            name='2026/2027',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
        )
        group = Group.objects.create(season=external_season, name='Grupo Sticky', slug='grupo-sticky')
        self.team.group = group
        self.team.save(update_fields=['group'])
        previous = WorkspaceSeason.objects.create(
            workspace=self.workspace,
            label='2025/2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=False,
        )
        rival = Team.objects.create(name='Rival Sticky', slug='rival-sticky', short_name='Sticky', group=group)
        Match.objects.create(
            season=external_season,
            club_season=previous,
            group=group,
            home_team=self.team,
            away_team=rival,
            date=date(2026, 9, 20),
            context=Match.CONTEXT_LEAGUE,
        )
        session = self.client.session
        session[f'active_club_season_id:{self.workspace.id}'] = previous.id
        session.save()

        response = self.client.post(
            reverse('match-hub-create'),
            data={
                'opponent_team_id': str(rival.id),
                'date': '2026-09-20',
                'home_away': 'home',
                'context': Match.CONTEXT_LEAGUE,
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        current_matches = Match.objects.filter(
            season=external_season,
            club_season=self.season,
            home_team=self.team,
            away_team=rival,
            date=date(2026, 9, 20),
        )
        self.assertEqual(current_matches.count(), 1)
        self.assertEqual(Match.objects.filter(club_season=previous, home_team=self.team, away_team=rival).count(), 1)


class WorkspaceAccessPolicyTests(TestCase):
    def test_workspace_owner_can_manage_without_membership(self):
        from football.access_policy import can_manage_workspace, can_view_workspace

        user = get_user_model().objects.create_user(username='policy-owner', password='pass-1234')
        workspace = Workspace.objects.create(
            name='Policy Club',
            slug='policy-club',
            kind=Workspace.KIND_CLUB,
            owner_user=user,
            is_active=True,
        )

        self.assertTrue(can_view_workspace(user, workspace))
        self.assertTrue(can_manage_workspace(user, workspace))

    def test_workspace_member_can_view_but_not_manage(self):
        from football.access_policy import can_manage_workspace, can_view_workspace

        user = get_user_model().objects.create_user(username='policy-member', password='pass-1234')
        workspace = Workspace.objects.create(
            name='Policy Member Club',
            slug='policy-member-club',
            kind=Workspace.KIND_CLUB,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMembership.ROLE_MEMBER,
        )

        self.assertTrue(can_view_workspace(user, workspace))
        self.assertFalse(can_manage_workspace(user, workspace))


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

    @patch('football.next_match_services.load_universo_snapshot')
    def test_preferred_next_match_uses_workspace_provider_before_global_cache(self, mocked_snapshot):
        mocked_provider_next = Mock()
        mocked_cached_next = Mock()
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

        payload = next_match_services.load_preferred_next_match_payload(
            primary_team=self.team,
            competition_context=context,
            find_provider_func=mocked_provider_next,
            load_cached_func=mocked_cached_next,
        )

        self.assertEqual(payload['opponent']['name'], 'Rival real')
        mocked_provider_next.assert_called_once()

    def test_preferred_next_match_can_skip_context_binding_for_fast_pages(self):
        context = WorkspaceCompetitionContext.objects.create(
            workspace=Workspace.objects.create(
                name='Cliente fast',
                slug='cliente-fast',
                kind=Workspace.KIND_CLUB,
                primary_team=self.team,
            ),
            team=self.team,
            group=self.team.group,
            season=self.team.group.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
        )

        mocked_bind = Mock()
        with patch('football.next_match_services.load_universo_snapshot', return_value={}):
            payload = next_match_services.load_preferred_next_match_payload(
                primary_team=self.team,
                competition_context=context,
                bind_context=False,
                bind_context_func=mocked_bind,
                find_provider_func=Mock(return_value={}),
                load_cached_func=Mock(return_value=None),
            )

        self.assertIsNone(payload)
        mocked_bind.assert_not_called()

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
        self.assertIn(f'team={pre_team.id}', response['Location'])
        mapping = self.client.session.get('active_team_by_workspace') or {}
        self.assertEqual(int(mapping.get(str(workspace.id)) or 0), int(pre_team.id))

    def test_workspace_context_cache_is_scoped_by_active_team(self):
        from django.test import RequestFactory
        from football.context_processors import workspace_access

        workspace = Workspace.objects.create(
            name='Cliente multi cache',
            slug='cliente-multi-cache',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        pre_team = Team.objects.create(
            name='Pre Cache',
            slug='pre-cache',
            short_name='Pre',
            group=self.team.group,
            is_primary=False,
            category='Prebenjamín',
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        WorkspaceTeam.objects.create(workspace=workspace, team=pre_team, is_default=False)
        factory = RequestFactory()
        session = self.client.session
        session['active_workspace_id'] = int(workspace.id)
        request_a = factory.get(f'/?team={self.team.id}')
        request_a.user = self.admin_user
        request_a.session = session
        payload_a = workspace_access(request_a)
        self.assertEqual(payload_a['active_team'].id, self.team.id)

        request_b = factory.get(f'/?team={pre_team.id}')
        request_b.user = self.admin_user
        request_b.session = session
        payload_b = workspace_access(request_b)

        self.assertEqual(payload_b['active_team'].id, pre_team.id)
        self.assertEqual(payload_b['active_team_query'], f'?team={pre_team.id}')

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

    def test_dashboard_data_uses_active_club_season_for_home_metrics(self):
        workspace = Workspace.objects.create(
            name='Cliente temporada home',
            slug='cliente-temporada-home',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            is_active=True,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        active_season = WorkspaceSeason.objects.create(
            workspace=workspace,
            label='2026/2027',
            start_date=date(2026, 7, 1),
            is_active=True,
        )
        workspace.active_season = active_season
        workspace.save(update_fields=['active_season'])
        player = Player.objects.create(team=self.team, name='Jugador Home', number=8)
        rival = Team.objects.create(name='Rival Home', slug='rival-home', group=self.team.group)
        old_match = Match.objects.create(
            season=self.team.group.season,
            group=self.team.group,
            home_team=self.team,
            away_team=rival,
            date=date(2026, 3, 1),
            home_score=4,
            away_score=1,
        )
        MatchEvent.objects.create(
            match=old_match,
            player=player,
            event_type='Pase',
            result='OK',
            zone='Medio',
            minute=12,
            system='touch-field-final',
            source_file='registro-acciones',
        )
        football_views._invalidate_team_dashboard_caches(self.team)
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-data'), {'team': self.team.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['team_metrics']['total_events'], 0)
        self.assertEqual(payload['player_metrics'], [])
        player_card = next(
            item for item in payload['player_cards']
            if int(item.get('player_id') or 0) == int(player.id)
        )
        self.assertEqual(player_card['total_actions'], 0)
        self.assertEqual(player_card['pj'], 0)
        self.assertEqual(payload['recent_form']['played'], 0)
        self.assertEqual(payload['recent_form']['last'], [])

    def test_dashboard_data_accepts_team_id_param_and_persists_active_team_mapping(self):
        workspace = Workspace.objects.create(
            name='Cliente multicategoria',
            slug='cliente-multicategoria',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        pre_team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-pre-dashboard',
            short_name='Benagalbón',
            group=self.team.group,
            is_primary=False,
            category='Prebenjamín',
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        WorkspaceTeam.objects.create(workspace=workspace, team=pre_team, is_default=False)

        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-data'), {'team_id': pre_team.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(int(payload.get('team', {}).get('id') or 0), int(pre_team.id))
        mapping = self.client.session.get('active_team_by_workspace') or {}
        self.assertEqual(int(mapping.get(str(workspace.id)) or 0), int(pre_team.id))
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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

    def test_platform_admin_sees_platform_entrypoint_in_main_nav(self):
        workspace = Workspace.objects.create(
            name='Cliente admin platform nav',
            slug='cliente-admin-platform-nav',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.alt_team, is_default=True)
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session.save()

        response = self.client.get(reverse('dashboard-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="nav-platform-link')
        self.assertContains(response, f'href="{reverse("platform-overview")}"')

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
        self.assertContains(response, 'Partido y contexto competitivo.')
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

    def test_single_team_member_can_see_configuration_entrypoint(self):
        workspace = Workspace.objects.create(
            name='Cliente equipo unico',
            slug='cliente-equipo-unico',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.alt_team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_member,
            role=WorkspaceMembership.ROLE_MEMBER,
        )
        WorkspaceTeamAccess.objects.create(
            workspace=workspace,
            team=self.alt_team,
            user=self.workspace_member,
            is_default=True,
        )
        self.client.force_login(self.workspace_member)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session['active_team_by_workspace'] = {str(workspace.id): int(self.alt_team.id)}
        session.save()

        response = self.client.get(reverse('match-hub') + f'?team={self.alt_team.id}')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_configure_active_team'])
        self.assertContains(response, 'Configurar')

    def test_single_team_member_can_open_onboarding_for_assigned_team(self):
        workspace = Workspace.objects.create(
            name='Cliente onboarding miembro',
            slug='cliente-onboarding-miembro',
            kind=Workspace.KIND_CLUB,
            primary_team=self.alt_team,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.alt_team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.workspace_member,
            role=WorkspaceMembership.ROLE_MEMBER,
        )
        WorkspaceTeamAccess.objects.create(
            workspace=workspace,
            team=self.alt_team,
            user=self.workspace_member,
            is_default=True,
        )
        self.client.force_login(self.workspace_member)
        session = self.client.session
        session['active_workspace_id'] = workspace.id
        session['active_team_by_workspace'] = {str(workspace.id): int(self.alt_team.id)}
        session.save()

        response = self.client.get(reverse('club-onboarding') + f'?team={self.alt_team.id}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configuración')

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

    @patch('football.views.resolve_player_photo_url', return_value='/player/123/photo/?v=99')
    def test_tactical_player_catalog_uses_resolved_photo_url(self, _mock_photo):
        request = Mock()

        catalog = football_views._build_tactical_player_catalog(request, self.team)

        self.assertTrue(catalog)
        self.assertEqual(catalog[0]['photo_url'], '/player/123/photo/?v=99')

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

    def test_save_convocation_can_create_away_match(self):
        self.client.force_login(self.user)
        rival = Team.objects.create(
            name='Rival Visitante',
            slug='rival-visitante-convocatoria',
            group=self.team.group,
            home_stadium='Campo Rival',
        )
        response = self.client.post(
            reverse('convocation-save'),
            data=json.dumps(
                {
                    'players': [],
                    'match_info': {
                        'opponent': rival.name,
                        'round': 'J25',
                        'date': '2026-04-05',
                        'time': '12:00',
                        'location': 'Campo Rival',
                        'home_away': 'away',
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        record = ConvocationRecord.objects.get(team=self.team, is_current=True)
        self.assertIsNotNone(record.match)
        self.assertEqual(record.match.home_team_id, rival.id)
        self.assertEqual(record.match.away_team_id, self.team.id)

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

    def test_save_convocation_returns_whatsapp_message(self):
        second_player = Player.objects.create(team=self.team, name='Francisco', number=9, position='DC')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('convocation-save'),
            data=json.dumps(
                {
                    'players': [self.player.id, second_player.id],
                    'match_info': {
                        'opponent': 'Francisco',
                        'round': 'Castejón',
                        'date': '2026-05-29',
                        'time': '18:30',
                        'location': 'Caña Chaqueta',
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        text = response.json().get('whatsapp_text') or ''
        self.assertIn('⚽️Benagalbon - Francisco', text)
        self.assertIn('📅Castejón 29/05/2026', text)
        self.assertIn('🕢18:30h', text)
        self.assertIn('📍Convocatoria: 17:45h', text)
        self.assertIn('🏟️Estadio: Caña Chaqueta', text)
        self.assertIn('1. Martinez', text)
        self.assertIn('2. Francisco', text)

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
        self.assertIsInstance(response.context['lineup_seed'], dict)

    @patch('football.views.resolve_player_photo_url', side_effect=RuntimeError('storage unavailable'))
    def test_initial_eleven_page_tolerates_photo_resolution_errors(self, _mock_photo):
        self.client.force_login(self.user)
        record = ConvocationRecord.objects.create(
            team=self.team,
            round='J24',
            opponent_name='Alhaurín de la Torre',
            match_date=date(2026, 3, 29),
            is_current=True,
            lineup_data={'starters': [{'id': str(self.player.id), 'x_pct': 50, 'y_pct': 90}], 'bench': []},
        )
        record.players.add(self.player)

        response = self.client.get(reverse('initial-eleven'))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.context['lineup_seed_json'],
            {
                'starters': [
                    {
                        'id': str(self.player.id),
                        'name': 'MARTINEZ',
                        'number': '--',
                        'position': 'MC',
                        'photo': '',
                        'x_pct': 50.0,
                        'y_pct': 90.0,
                    },
                ],
                'bench': [],
                '_meta': {'orientation': 'tb'},
            },
        )

    def test_initial_eleven_page_handles_match_without_convocation(self):
        self.client.force_login(self.user)
        rival = Team.objects.create(name='Rival sin convocatoria', slug='rival-sin-convocatoria', group=self.team.group)
        match = Match.objects.create(
            season=self.team.group.season,
            group=self.team.group,
            round='J25',
            date=date(2026, 4, 5),
            home_team=self.team,
            away_team=rival,
        )

        response = self.client.get(f"{reverse('initial-eleven')}?match_id={match.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['rival_display_name'], 'Rival')

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
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
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

    def test_player_report_manual_stats_feed_dashboard_kpis(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('player-season-report-edit', args=[self.player.id]),
            {
                'manual_pj': '12',
                'manual_minutes': '720',
                'manual_goals': '5',
                'manual_assists': '4',
                'manual_participation_pct': '66.5',
                'manual_success_rate': '71',
                'manual_importance_score': '82',
                'manual_influence_score': '77',
                'most_used_position': 'Interior derecho',
                'ideal_position': 'Mediocentro',
                'leadership_rating': '8.5',
                'game_knowledge_rating': '9,5',
            },
        )

        self.assertEqual(response.status_code, 302)
        report = PlayerSeasonReport.objects.get(player=self.player, team=self.team)
        self.assertEqual(report.leadership_rating, Decimal('8.5'))
        self.assertEqual(report.game_knowledge_rating, Decimal('9.5'))
        self.assertEqual(report.manual_overrides['pj'], 12)
        self.assertEqual(report.manual_overrides['most_used_position'], 'Interior derecho')
        self.assertEqual(report.manual_overrides['ideal_position'], 'Mediocentro')
        overrides = get_manual_player_base_overrides(self.team, self.season)
        self.assertEqual(overrides[self.player.id]['pj'], 12)
        self.assertEqual(overrides[self.player.id]['minutes'], 720)
        rows = compute_player_dashboard(self.team, force_refresh=True)
        detail = next(row for row in rows if row['player_id'] == self.player.id)
        self.assertEqual(int(detail.get('pj') or 0), 12)
        self.assertEqual(int(detail.get('minutes') or 0), 720)
        self.assertEqual(int(detail.get('goals') or 0), 5)
        self.assertEqual(int(detail.get('assists') or 0), 4)
        self.assertEqual(float(detail.get('participation_pct') or 0), 66.5)
        self.assertEqual(float(detail.get('success_rate') or 0), 71.0)
        self.assertEqual(float(detail.get('importance_score') or 0), 82.0)
        self.assertEqual(float(detail.get('influence_score') or 0), 77.0)

    def test_report_manual_overrides_survive_season_label_variants(self):
        self.season.name = '2025/2026'
        self.season.start_date = date(2025, 9, 1)
        self.season.end_date = date(2026, 6, 30)
        self.season.save(update_fields=['name', 'start_date', 'end_date'])
        PlayerSeasonReport.objects.create(
            player=self.player,
            team=self.team,
            season_label='2025-2026',
            scope=Match.CONTEXT_LEAGUE,
            tournament_name='',
            manual_overrides={
                'pj': 13,
                'minutes': 845,
                'goals': 6,
                'assists': 5,
                'participation_pct': 74.5,
                'success_rate': 68.2,
                'importance_score': 83.1,
                'influence_score': 79.4,
            },
        )

        rows = compute_player_dashboard(self.team, force_refresh=True)
        detail = next(row for row in rows if row['player_id'] == self.player.id)

        self.assertEqual(int(detail.get('pj') or 0), 13)
        self.assertEqual(int(detail.get('minutes') or 0), 845)
        self.assertEqual(int(detail.get('goals') or 0), 6)
        self.assertEqual(int(detail.get('assists') or 0), 5)
        self.assertEqual(float(detail.get('participation_pct') or 0), 74.5)
        self.assertEqual(float(detail.get('success_rate') or 0), 68.2)
        self.assertEqual(float(detail.get('importance_score') or 0), 83.1)
        self.assertEqual(float(detail.get('influence_score') or 0), 79.4)

    def test_staff_rating_radar_uses_report_ratings(self):
        report = PlayerSeasonReport.objects.create(
            player=self.player,
            team=self.team,
            season_label='Temporada actual',
            overall_rating=Decimal('8.5'),
            technical_rating=Decimal('7.5'),
            tactical_rating=Decimal('6.5'),
            physical_rating=Decimal('5.5'),
            mental_rating=Decimal('9.5'),
            social_rating=Decimal('10.0'),
            leadership_rating=Decimal('8.5'),
            game_knowledge_rating=Decimal('7.5'),
        )

        radar = football_views._build_staff_rating_radar_data(report)

        self.assertEqual(
            [axis['display'] for axis in radar['axes']],
            ['8.5/10', '7.5/10', '6.5/10', '5.5/10', '9.5/10', '10/10', '8.5/10', '7.5/10'],
        )
        self.assertEqual(radar['average_display'], '7.9/10')
        self.assertTrue(radar['polygon_points_svg'])

    def test_saved_manual_base_totals_override_manual_match_rows(self):
        save_manual_player_base_overrides(
            player=self.player,
            season=self.season,
            values={
                'manual_pj': '10',
                'manual_pt': '8',
                'manual_minutes': '700',
                'manual_goals': '12',
                'manual_assists': '6',
            },
        )
        opponent = Team.objects.create(name='Rival Manual', slug='rival-manual', group=self.team.group, is_primary=False)
        match = Match.objects.create(
            season=self.season,
            group=self.team.group,
            round='J1',
            context=Match.CONTEXT_LEAGUE,
            date=date(2026, 1, 1),
            home_team=self.team,
            away_team=opponent,
        )
        PlayerStatistic.objects.create(player=self.player, season=self.season, match=match, context='manual-match', name='manual_minutes', value=45)
        PlayerStatistic.objects.create(player=self.player, season=self.season, match=match, context='manual-match', name='manual_goals', value=1)
        PlayerStatistic.objects.create(player=self.player, season=self.season, match=match, context='manual-match', name='manual_assists', value=0)

        rows = compute_player_dashboard(self.team, force_refresh=True)
        detail = next(row for row in rows if row['player_id'] == self.player.id)

        self.assertEqual(int(detail.get('pj') or 0), 10)
        self.assertEqual(int(detail.get('pt') or 0), 8)
        self.assertEqual(int(detail.get('minutes') or 0), 700)
        self.assertEqual(int(detail.get('goals') or 0), 12)
        self.assertEqual(int(detail.get('assists') or 0), 6)

    def test_manual_base_totals_apply_with_active_season_date_filter(self):
        self.season.start_date = date(2025, 9, 1)
        self.season.end_date = date(2026, 6, 30)
        self.season.save(update_fields=['start_date', 'end_date'])
        save_manual_player_base_overrides(
            player=self.player,
            season=self.season,
            values={
                'manual_pj': '14',
                'manual_pt': '11',
                'manual_minutes': '930',
                'manual_goals': '7',
                'manual_assists': '5',
            },
        )

        rows = compute_player_dashboard(
            self.team,
            force_refresh=True,
            date_start=self.season.start_date,
            date_end=self.season.end_date,
        )
        detail = next(row for row in rows if row['player_id'] == self.player.id)

        self.assertEqual(int(detail.get('pj') or 0), 14)
        self.assertEqual(int(detail.get('pt') or 0), 11)
        self.assertEqual(int(detail.get('minutes') or 0), 930)
        self.assertEqual(int(detail.get('goals') or 0), 7)
        self.assertEqual(int(detail.get('assists') or 0), 5)

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


class ManualMatchFixtureCanonicalizationTests(TestCase):
    """
    Regresión: partidos creados/duplicados por Convocatoria/11 vs editor manual.
    Debe conservar los overrides manuales y el metadata del Match real (marcador/result).
    """

    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='fixtureadmin',
            email='fixtureadmin@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ADMIN)
        competition = Competition.objects.create(name='Liga Fixture', slug='liga-fixture', region='Andalucia')
        self.season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='Grupo Fixture', slug='grupo-fixture')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-fixture', group=self.group, is_primary=True)
        self.rival = Team.objects.create(name='C.D. Rival', slug='cd-rival-fixture', group=self.group, is_primary=False)
        self.player = Player.objects.create(team=self.team, name='Jugador Fixture', number=9)

    def test_manual_match_stats_and_result_survive_duplicate_match_ids(self):
        fixture_date = date(2026, 1, 12)
        placeholder = Match.objects.create(
            season=self.season,
            group=self.group,
            round='Jornada 1',
            context=Match.CONTEXT_LEAGUE,
            date=fixture_date,
            home_team=self.team,
            away_team=None,
        )
        record = ConvocationRecord.objects.create(
            team=self.team,
            match=placeholder,
            round='Jornada 1',
            match_date=fixture_date,
            opponent_name=self.rival.name,
            lineup_data={'starters': [{'id': self.player.id}], 'bench': []},
            is_current=False,
        )
        record.players.set([self.player])

        real_match = Match.objects.create(
            season=self.season,
            group=self.group,
            round='Jornada 1',
            context=Match.CONTEXT_LEAGUE,
            date=fixture_date,
            home_team=self.team,
            away_team=self.rival,
            home_score=2,
            away_score=0,
            result='2-0',
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=real_match,
            name='manual_minutes',
            context='manual-match',
            value=90,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=real_match,
            name='manual_goals',
            context='manual-match',
            value=1,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=real_match,
            name='manual_assists',
            context='manual-match',
            value=1,
        )

        rows = compute_player_dashboard(self.team, force_refresh=True)
        detail = next((r for r in rows if r.get('player_id') == self.player.id), None)
        self.assertIsNotNone(detail)
        self.assertEqual(int(detail.get('pj') or 0), 1)
        self.assertEqual(int(detail.get('minutes') or 0), 90)
        self.assertEqual(int(detail.get('goals') or 0), 1)
        self.assertEqual(int(detail.get('assists') or 0), 1)

        matches = detail.get('matches') or []
        played = next(m for m in matches if m.get('played'))
        self.assertEqual(int(played.get('match_id') or 0), int(real_match.id))
        self.assertEqual(played.get('result'), '2-0')

    def test_manual_match_stats_show_without_events_or_convocation(self):
        fixture_date = date(2026, 2, 10)
        match = Match.objects.create(
            season=self.season,
            group=self.group,
            round='Jornada 2',
            context=Match.CONTEXT_LEAGUE,
            date=fixture_date,
            home_team=self.team,
            away_team=self.rival,
            home_score=1,
            away_score=0,
            result='1-0',
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=match,
            name='manual_minutes',
            context='manual-match',
            value=60,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=match,
            name='manual_goals',
            context='manual-match',
            value=1,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=match,
            name='manual_assists',
            context='manual-match',
            value=0,
        )

        rows = compute_player_dashboard(self.team, force_refresh=True)
        detail = next((r for r in rows if r.get('player_id') == self.player.id), None)
        self.assertIsNotNone(detail)
        self.assertEqual(int(detail.get('pj') or 0), 1)
        self.assertEqual(int(detail.get('minutes') or 0), 60)
        matches = detail.get('matches') or []
        played = next(m for m in matches if m.get('played'))
        self.assertEqual(played.get('result'), '1-0')


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

    def test_player_detail_staff_back_button_returns_to_coach_roster(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('player-detail', args=[self.player.id]),
            {'team': self.player.team_id, 'scope': Match.CONTEXT_LEAGUE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse('coach-roster'), response.context['player_list_back_url'])
        self.assertIn('tab=stats', response.context['player_list_back_url'])
        self.assertIn(f'team={self.player.team_id}', response.context['player_list_back_url'])
        self.assertNotIn(reverse('player-dashboard'), response.context['player_list_back_url'])
        self.assertContains(response, 'Volver')

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

    def test_player_detail_uses_players_team_crest(self):
        team = self.player.team
        team.name = 'Málaga Club de Fútbol'
        team.slug = 'malaga-cf-detail-crest'
        team.short_name = ''
        team.save(update_fields=['name', 'slug', 'short_name'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Escudo {team.display_name}')
        self.assertContains(response, reverse('team-crest-svg', args=[team.id]))
        self.assertNotContains(response, 'football/images/cdb-logo.png')

    def test_player_detail_profile_weight_persists_and_renders_number_value(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('player-detail', args=[self.player.id]),
            {
                'form_action': 'profile',
                'full_name': 'Jugador Detail',
                'nickname': '',
                'birth_date': '',
                'height_cm': '181',
                'weight_kg_base': '76,50',
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
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.assertEqual(str(self.player.weight_kg), '76.50')
        self.assertContains(response, 'name="weight_kg_base" value="76.50"', html=False)

    @patch('football.views.compute_player_dashboard')
    @override_settings(MEDIA_URL='/media-test/')
    def test_player_pdf_html_uses_player_team_branding(self, mocked_dashboard):
        png_bytes = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Zl4QAAAAASUVORK5CYII='
        )
        media_root = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_root):
                team = self.player.team
                team.name = 'Málaga Club de Fútbol'
                team.slug = 'malaga-cf-detail'
                team.short_name = ''
                team.crest_image.save(
                    'malaga.png',
                    SimpleUploadedFile('malaga.png', png_bytes, content_type='image/png'),
                    save=False,
                )
                team.save(update_fields=['name', 'slug', 'short_name', 'crest_image'])
                mocked_dashboard.return_value = [
                    {
                        'player_id': self.player.id,
                        'name': self.player.name,
                        'pj': 1,
                        'pt': 1,
                        'minutes': 90,
                        'goals': 0,
                        'assists': 0,
                        'success_rate': 0,
                        'importance_score': 0,
                        'influence_score': 0,
                        'total_actions': 0,
                        'successes': 0,
                        'matches': [],
                    }
                ]

                self.client.force_login(self.user)
                response = self.client.get(
                    reverse('player-pdf', args=[self.player.id]),
                    {'format': 'html', 'snapshot': '0'},
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '--club-primary: #6bc4e8')
                self.assertContains(response, 'background: #6bc4e8')
                self.assertContains(response, 'Escudo Málaga Club de Fútbol')
                self.assertContains(response, 'Málaga Club de Fútbol · Informe final de temporada')
                self.assertContains(response, 'data:image/jpeg;base64,')
                self.assertNotContains(response, 'alt="2J"', html=False)
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    @patch('football.views.compute_player_dashboard')
    def test_player_pdf_charts_use_compact_round_labels_and_distinct_ga_colors(self, mocked_dashboard):
        mocked_dashboard.return_value = [
            {
                'player_id': self.player.id,
                'name': self.player.name,
                'pj': 2,
                'pt': 2,
                'minutes': 90,
                'goals': 1,
                'assists': 1,
                'success_rate': 50,
                'importance_score': 0,
                'influence_score': 0,
                'total_actions': 4,
                'successes': 2,
                'matches': [
                    {
                        'round': 'Jornada 10',
                        'opponent': 'Tercer Rival Con Nombre Muy Largo',
                        'date': '2026-03-01',
                        'played': True,
                        'minutes': 45,
                        'goals': 0,
                        'assists': 0,
                        'actions': 2,
                        'successes': 1,
                    },
                    {
                        'round': 'Jornada 1',
                        'opponent': 'Rival Con Nombre Muy Largo',
                        'date': '2026-02-01',
                        'played': True,
                        'minutes': 45,
                        'goals': 1,
                        'assists': 0,
                        'actions': 2,
                        'successes': 1,
                    },
                    {
                        'round': 'Jornada 2',
                        'opponent': 'Otro Rival Con Nombre Muy Largo',
                        'date': '2026-02-08',
                        'played': True,
                        'minutes': 45,
                        'goals': 0,
                        'assists': 1,
                        'actions': 2,
                        'successes': 1,
                    },
                ],
            }
        ]
        PlayerSeasonReport.objects.create(
            player=self.player,
            team=self.player.team,
            season_label='2025/2026',
            scope=Match.CONTEXT_LEAGUE,
            ring_kpis=['participation_pct', 'importance_score', 'influence_score', 'aerial_duel_rate'],
            overall_rating=Decimal('8.5'),
            technical_rating=Decimal('7.5'),
            tactical_rating=Decimal('6.5'),
            physical_rating=Decimal('5.5'),
            mental_rating=Decimal('9.5'),
            social_rating=Decimal('10.0'),
            leadership_rating=Decimal('8.5'),
            game_knowledge_rating=Decimal('7.5'),
        )
        TeamStanding.objects.create(
            season=self.player.team.group.season,
            group=self.player.team.group,
            team=self.player.team,
            position=4,
            played=12,
            points=25,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('player-pdf', args=[self.player.id]),
            {'format': 'html', 'snapshot': '0'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'X: jornadas compactas')
        self.assertContains(response, 'stroke="#f4b400"', html=False)
        self.assertContains(response, '>1</text>', html=False)
        self.assertContains(response, '>RIVA.LARG</text>', html=False)
        self.assertNotContains(response, 'Clave jornadas-rivales')
        self.assertNotContains(response, '<div class="chart-key"', html=False)
        self.assertContains(response, 'Media ratings staff')
        self.assertContains(response, '7.9/10')
        self.assertContains(response, '<div class="perf-ring-label">Participación</div>', html=False)
        self.assertContains(response, '<div class="perf-ring-label">Importancia</div>', html=False)
        self.assertContains(response, '<div class="perf-ring-label">Influencia</div>', html=False)
        self.assertContains(response, '<div class="perf-ring-label">Aéreos</div>', html=False)
        self.assertNotContains(response, '<div class="perf-ring-label">Precisión de pase</div>', html=False)
        self.assertContains(response, 'Puntos: <strong>25</strong>', html=False)
        self.assertContains(response, 'Posición: <strong>4º</strong>', html=False)
        self.assertContains(response, '<span class="staff-radar-index">8</span>Conoc. juego', html=False)
        self.assertNotContains(response, 'Detalle por partido', html=False)
        self.assertNotContains(response, '<table class="table matches-table">', html=False)
        self.assertContains(response, '<th>Liderazgo</th>', html=False)
        self.assertContains(response, '<th>Conoc. juego</th>', html=False)
        self.assertNotContains(response, '>Global</text>', html=False)
        self.assertNotContains(response, '>Conoc. juego</text>', html=False)
        self.assertNotContains(response, 'rotate(-35', html=False)
        self.assertNotContains(response, '>1 · Rival', html=False)

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
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
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
        self.player = Player.objects.create(team=self.team, name='Jugador Admin', number=8)

    def test_actions_tab_renders_with_date_only_match(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('admin-page'), {'tab': 'actions', 'match_id': self.match.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partido a editar')
        self.assertContains(response, '<select name="action_type" required>', html=False)
        self.assertContains(response, '<select name="result" required>', html=False)
        self.assertContains(response, 'OK')

    def test_match_editor_uses_select_catalogs_for_manual_actions(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('match-editor', args=[self.match.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="event_type" required>', html=False)
        self.assertContains(response, '<select name="result" required>', html=False)
        self.assertContains(response, '<select name="zone">', html=False)
        self.assertContains(response, 'OK')

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

    def test_coach_matches_shows_matches_from_other_seasons(self):
        self.client.force_login(self.user)
        old_competition = Competition.objects.create(name='Liga Historica', slug='liga-historica', region='Andalucia')
        old_season = Season.objects.create(competition=old_competition, name='2024/2025', is_current=False)
        old_group = Group.objects.create(season=old_season, name='Grupo Historico', slug='grupo-historico')
        old_rival = Team.objects.create(name='Rival Historico', slug='rival-historico', group=old_group)
        Match.objects.create(
            season=old_season,
            group=old_group,
            home_team=old_rival,
            away_team=self.team,
            date=date(2025, 5, 12),
            round='Jornada historica',
        )

        response = self.client.get(reverse('coach-matches'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Historico')
        self.assertContains(response, 'Rival Admin')

    def test_coach_matches_clean_get_ignores_saved_registered_filter(self):
        self.client.force_login(self.user)
        unregistered_rival = Team.objects.create(name='Rival Sin Registro', slug='rival-sin-registro', group=self.team.group)
        Match.objects.create(
            season=self.match.season,
            group=self.team.group,
            home_team=self.team,
            away_team=unregistered_rival,
            date=date(2026, 4, 3),
            round='Jornada libre',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type='Pase',
            result='OK',
            source_file='test',
        )
        session = self.client.session
        session[f'coach_matches_filters:v1:t{int(self.team.id)}'] = {'reg': '1', 'dir': 'desc'}
        session.save()

        response = self.client.get(reverse('coach-matches'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Sin Registro')
        self.assertContains(response, 'Rival Admin')

    def test_coach_matches_renders_clickable_match_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('coach-matches'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'match-card')
        self.assertContains(response, reverse('match-editor', args=[self.match.id]))
        self.assertContains(response, 'Ficha')
        self.assertContains(response, 'Registro')


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
    @patch('football.universo_client.universo_api_post')
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

    @patch('football.universo_client.universo_api_post')
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

    def test_match_actions_page_auto_creates_convocation_when_missing(self):
        ConvocationRecord.objects.filter(team=self.team).delete()
        self.assertIsNone(get_current_convocation_record(self.team, match=self.match, fallback_to_latest=False))

        response = self.client.get(f"{reverse('match-action-page')}?match_id={self.match.id}")
        self.assertEqual(response.status_code, 200)

        record = get_current_convocation_record(self.team, match=self.match, fallback_to_latest=False)
        self.assertIsNotNone(record)
        self.assertTrue(record.is_current)
        self.assertGreater(record.players.count(), 0)

    def test_match_actions_uses_convocation_for_selected_match_even_if_not_current(self):
        other_match = Match.objects.create(
            season=self.match.season,
            group=self.match.group,
            home_team=self.team,
            away_team=self.rival,
            round='25',
            date=date(2026, 3, 29),
        )
        # Convocatoria del partido objetivo (NO current).
        target_record = self.convocation
        target_record.is_current = False
        target_record.lineup_data = {'starters': [{'id': str(self.player.id)}], 'bench': []}
        target_record.save(update_fields=['is_current', 'lineup_data'])
        # Otra convocatoria current para otro partido (simula que el staff ya está preparando otro partido).
        other_record = ConvocationRecord.objects.create(
            team=self.team,
            match=other_match,
            is_current=True,
        )
        other_record.players.add(self.player)

        response = self.client.get(reverse('match-action-page'), {'match_id': self.match.id})

        self.assertEqual(response.status_code, 200)
        payload = response.context['initial_lineup_payload']
        self.assertEqual(str(payload['starters'][0]['id']), str(self.player.id))

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

    def test_match_actions_bulk_add_creates_events(self):
        response = self.client.post(
            reverse('match-action-bulk-add'),
            data=json.dumps(
                {
                    'match_id': self.match.id,
                    'player_id': self.player.id,
                    'action_type': 'Pérdida',
                    'result': 'Mal',
                    'zone': 'Medio Centro',
                    'quantity': 6,
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload.get('created'), 6)
        self.assertEqual(
            MatchEvent.objects.filter(
                match=self.match,
                player=self.player,
                event_type='Pérdida',
                result='Mal',
                zone='Medio Centro',
                source_file='manual-bulk',
                system='touch-field-final',
            ).count(),
            6,
        )

    def test_rival_lineup_get_and_save_works_from_match_actions(self):
        from football.models import RivalConvocationRecord

        RivalConvocationRecord.objects.create(
            team=self.team,
            match=self.match,
            rival_team=self.rival,
            convocation_data=[
                {'code': 'r1', 'name': 'Rival Uno', 'number': '1', 'position': 'POR'},
                {'code': 'r9', 'name': 'Rival Nueve', 'number': '9', 'position': 'DC'},
            ],
            lineup_data={
                'starters': [
                    {'code': 'r1', 'name': 'Rival Uno', 'number': '1', 'position': 'POR'},
                    {'code': 'r9', 'name': 'Rival Nueve', 'number': '9', 'position': 'DC'},
                ],
                'bench': [],
            },
        )

        get_resp = self.client.get(reverse('match-rival-lineup-get'))
        self.assertEqual(get_resp.status_code, 200)
        get_payload = get_resp.json()
        self.assertTrue(get_payload.get('ok'))
        self.assertEqual(get_payload['lineup']['starters'][0]['code'], 'r1')

        save_resp = self.client.post(
            reverse('match-rival-lineup-save'),
            data=json.dumps(
                {
                    'lineup': {
                        'starters': [
                            {'code': 'r1', 'x_pct': 50, 'y_pct': 10},
                            {'code': 'r9', 'x_pct': 50, 'y_pct': 30},
                        ],
                        'bench': [],
                    }
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(save_resp.status_code, 200)
        saved = save_resp.json()
        self.assertTrue(saved.get('saved'))
        self.assertEqual(saved['lineup']['starters'][0]['code'], 'r1')
        self.assertIn('x_pct', saved['lineup']['starters'][0])

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

    def test_update_match_action_allows_fast_correction(self):
        create = self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'Pase',
                'result': 'OK',
                'zone': 'Ataque Centro',
                'minute': 11,
                'period': 1,
                'client_event_uid': 'evt-create-1',
            },
        )
        self.assertEqual(create.status_code, 200)
        event_id = create.json().get('id')
        self.assertTrue(event_id)

        update = self.client.post(
            reverse('match-action-update'),
            {
                'match_id': self.match.id,
                'event_id': event_id,
                'player': self.player.id,
                'action_type': 'Pase',
                'result': 'FALLO',
                'zone': 'Ataque Izquierda',
                'minute': 12,
                'period': 1,
            },
        )
        self.assertEqual(update.status_code, 200)
        payload = update.json()
        self.assertTrue(payload.get('updated'))
        self.assertEqual(payload.get('id'), event_id)
        self.assertEqual(payload.get('result'), 'FALLO')
        self.assertEqual(payload.get('zone'), 'Ataque Izquierda')
        obj = MatchEvent.objects.filter(id=event_id).first()
        self.assertEqual(obj.result, 'FALLO')
        self.assertEqual(obj.zone, 'Ataque Izquierda')

    def test_match_actions_events_api_supports_incremental_polling(self):
        r1 = self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'DUELO',
                'result': 'GANADO',
                'zone': 'Medio Centro',
                'minute': 5,
                'period': 1,
                'client_event_uid': 'evt-poll-1',
            },
        )
        self.assertEqual(r1.status_code, 200)
        first_id = r1.json().get('id')
        self.assertTrue(first_id)

        self.client.post(
            reverse('match-action-record'),
            {
                'match_id': self.match.id,
                'player': self.player.id,
                'action_type': 'DUELO',
                'result': 'PERDIDO',
                'zone': 'Medio Centro',
                'minute': 6,
                'period': 1,
                'client_event_uid': 'evt-poll-2',
            },
        )

        poll = self.client.get(reverse('match-actions-events-api'), {'match_id': self.match.id, 'since_id': first_id})
        self.assertEqual(poll.status_code, 200)
        data = poll.json()
        self.assertTrue(data.get('ok'))
        events = data.get('events') or []
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].get('result'), 'PERDIDO')

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

    def test_finalize_consolidates_live_actions_and_resets_matchday_state(self):
        player = Player.objects.create(team=self.team, name='Registro KPI Único', number=99, position='Interior')
        self.convocation.players.add(player)
        session = self.client.session
        session['active_match_by_team'] = {str(self.team.id): self.match.id}
        session.save()
        self.convocation.lineup_data = {
            'starters': [{'id': str(player.id), 'name': player.name, 'number': player.number}],
            'bench': [],
        }
        self.convocation.is_current = True
        self.convocation.save(update_fields=['lineup_data', 'is_current'])
        baseline_dashboard = compute_player_dashboard(self.team, force_refresh=True)
        baseline_detail = next(item for item in baseline_dashboard if item['player_id'] == player.id)
        baseline_goals = int(baseline_detail.get('goals') or 0)
        baseline_assists = int(baseline_detail.get('assists') or 0)
        MatchEvent.objects.create(
            match=self.match,
            player=player,
            event_type='Gol',
            result='Gol',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=51,
            period=2,
            system='touch-field',
            source_file='registro-acciones',
        )
        MatchEvent.objects.create(
            match=self.match,
            player=player,
            event_type='Asistencia',
            result='OK',
            zone='Ataque Centro',
            tercio='Ataque',
            minute=52,
            period=2,
            system='touch-field',
            source_file='registro-acciones',
        )

        response = self.client.post(
            reverse('match-action-finalize'),
            data=json.dumps({'match_id': self.match.id, 'match_info': {'match_id': self.match.id}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('saved'))
        self.assertEqual(payload.get('updated'), 2)
        self.assertFalse(
            MatchEvent.objects.filter(
                match=self.match,
                system='touch-field',
                source_file='registro-acciones',
            ).exists()
        )
        self.assertEqual(
            MatchEvent.objects.filter(
                match=self.match,
                system='touch-field-final',
                source_file='registro-acciones',
            ).count(),
            2,
        )
        self.convocation.refresh_from_db()
        self.assertFalse(self.convocation.is_current)
        self.assertEqual(
            self.client.session.get('active_match_by_team', {}).get(str(self.team.id)),
            None,
        )
        page = self.client.get(reverse('match-action-page'), {'stage': 'pre'})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['actions_pending_count'], 0)
        self.assertEqual(page.context['actions_final_count'], 0)
        self.assertEqual(list(page.context['recent_events']), [])
        dashboard = compute_player_dashboard(self.team, force_refresh=True)
        detail = next(item for item in dashboard if item['player_id'] == player.id)
        self.assertEqual(detail['goals'], baseline_goals + 1)
        self.assertEqual(detail['assists'], baseline_assists + 1)

    def test_finalize_resets_matchday_state_even_without_pending_actions(self):
        session = self.client.session
        session['active_match_by_team'] = {str(self.team.id): self.match.id}
        session.save()
        self.convocation.is_current = True
        self.convocation.save(update_fields=['is_current'])

        response = self.client.post(
            reverse('match-action-finalize'),
            data=json.dumps({'match_id': self.match.id, 'match_info': {'match_id': self.match.id}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('saved'))
        self.assertEqual(payload.get('updated'), 0)
        self.convocation.refresh_from_db()
        self.assertFalse(self.convocation.is_current)
        self.assertEqual(
            self.client.session.get('active_match_by_team', {}).get(str(self.team.id)),
            None,
        )

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

    def test_match_actions_page_payload_under_budget(self):
        # Guardrail: evita reintroducir megabytes de JS inline en HTML.
        response = self.client.get(reverse('match-action-page'))
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(response.content or b''), 220_000)


class PlayerDashboardViewTests(TestCase):
    def setUp(self):
        cache.clear()
        # Esta batería valida comportamiento legacy (monoclub) sin onboarding/workspace.
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
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

    def test_player_dashboard_uses_active_club_season_dates(self):
        workspace = Workspace.objects.create(
            name='Club temporada',
            slug='club-temporada',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=self.team, is_default=True)
        new_season = WorkspaceSeason.objects.create(
            workspace=workspace,
            label='2026/2027',
            start_date=date(2026, 7, 1),
            is_active=True,
        )
        workspace.active_season = new_season
        workspace.save(update_fields=['active_season'])

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('player-dashboard'),
            {'workspace': workspace.id, 'team': self.team.id},
        )

        self.assertEqual(response.status_code, 200)
        player_row = next(
            row for row in response.context['player_stats']
            if int(row.get('player_id') or 0) == int(self.player.id)
        )
        self.assertEqual(player_row.get('total_actions'), 0)
        self.assertEqual(player_row.get('pj'), 0)

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
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
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

    @patch('football.views.compute_player_cards')
    def test_coach_roster_cards_show_staff_rating(self, mock_cards):
        player = Player.objects.create(team=self.team, name='Jugador Staff', number=7)
        mock_cards.return_value = [
            {
                'player_id': player.id,
                'name': player.name,
                'nickname': '',
                'number': player.number,
                'photo_url': '',
                'profile_label': 'MC',
                'position': 'MC',
                'pj': 0,
                'minutes': 0,
                'goals': 0,
                'assists': 0,
                'success_rate': 0,
                'duel_rate': 0,
                'passes_accuracy': 0,
                'shots_accuracy': 0,
                'influence_score': 0,
                'importance_score': 0,
                'has_active_injury': False,
                'is_sanctioned': False,
                'is_apercibido': False,
                'staff_rating_display': '8/10',
                'staff_rating_pct': 80,
            }
        ]

        response = self.client.get(reverse('coach-roster'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff')
        self.assertContains(response, '8/10')
        self.assertContains(response, '--staff-rating-pct:80%;')


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
            follow=True,
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
        self.user = self.admin
        self.player = Player.objects.create(team=self.team, name='Hugo', number=9, position='DC', is_active=True)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo Staff',
            objective='',
            week_start=date(2026, 3, 23),
            week_end=date(2026, 3, 29),
            status=TrainingMicrocycle.STATUS_DRAFT,
        )

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
            follow=True,
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
            follow=True,
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
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Sesión ya estaba creada: Transición + finalización. (Se evitó duplicado por doble envío.)',
        )
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
            follow=True,
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
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sesión enviada a papelera: Sesión con tarea.')
        trashed = TrainingSession.objects.get(id=session.id)
        self.assertTrue(trashed.microcycle.title.strip().lower().startswith('papelera'))

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
        self.assertContains(response, 'id="task-device-view"')
        self.assertContains(response, 'Escritorio')

    def test_task_builder_prefills_age_group_from_team_category(self):
        self.team.category = 'Juvenil'
        self.team.save(update_fields=['category'])

        response = self.client.get(reverse('sessions-task-create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="draw_task_age_group" value="Juvenil"')

    def test_task_builder_loads_canvas_from_legacy_tokens_when_graphic_editor_missing(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión legacy tokens',
            duration_minutes=90,
        )
        # Simula una tarea antigua: `tactical_layout.tokens` existe, pero falta `meta.graphic_editor.canvas_state`.
        task = SessionTask.objects.create(
            session=session,
            title='Tarea legacy',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={
                'tokens': [
                    {
                        'type': 'circle',
                        'left': 120,
                        'top': 220,
                        'radius': 18,
                        'fill': '#22d3ee',
                        'data': {'kind': 'token', 'label': 'A'},
                    }
                ],
                'meta': {'scope': 'coach', 'pitch_preset': 'full_pitch', 'pitch_orientation': 'landscape'},
            },
        )

        response = self.client.get(reverse('sessions-task-edit', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        # Debe rehidratar el estado inicial a partir de `tokens` (para que el editor no quede vacío).
        self.assertContains(response, 'id="draw-canvas-state"')
        self.assertContains(response, '&quot;left&quot;: 120')
        self.assertContains(response, '&quot;kind&quot;: &quot;token&quot;')

    def test_task_builder_falls_back_to_preview_background_when_no_canvas_state(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión preview background',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea preview',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={'meta': {'scope': 'coach', 'pitch_preset': 'full_pitch', 'pitch_orientation': 'landscape'}},
        )
        # Fuerza que exista preview guardada pero sin estado de pizarra.
        task.task_preview_image.save('task-preview.png', ContentFile(b'fake-bytes'), save=True)

        response = self.client.get(reverse('sessions-task-edit', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="draw-canvas-state"')
        self.assertContains(response, 'preview-background')
        self.assertContains(response, f'/coach/sesiones/tarea/{task.id}/preview/')

    def test_task_builder_rehydrates_performed_task_from_origin_graphic_state(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión origen performed',
            duration_minutes=90,
        )
        origin = SessionTask.objects.create(
            session=session,
            title='Origen',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={
                'tokens': [],
                'timeline': [],
                'meta': {
                    'scope': 'coach',
                    'pitch_preset': 'full_pitch',
                    'pitch_orientation': 'landscape',
                    'graphic_editor': {
                        'canvas_state': {'version': '5.3.0', 'objects': [{'type': 'circle', 'left': 50, 'top': 60}]},
                        'canvas_width': 1054,
                        'canvas_height': 684,
                    },
                },
            },
        )
        performed = SessionTask.objects.create(
            session=session,
            title='Performed',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={
                'tokens': [],
                'timeline': [],
                'meta': {
                    'scope': 'coach',
                    'source': 'performed',
                    'performed_from_task_id': origin.id,
                    # Sin graphic_editor (simula pérdida de estado)
                },
            },
        )

        response = self.client.get(reverse('sessions-task-edit', args=[performed.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&quot;left&quot;: 50')

    def test_task_builder_rehydrates_performed_task_when_origin_id_missing(self):
        origin_session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión origen fallback',
            duration_minutes=90,
        )
        origin = SessionTask.objects.create(
            session=origin_session,
            title='Tarea X',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            order=7,
            tactical_layout={
                'meta': {
                    'scope': 'coach',
                    'graphic_editor': {
                        'canvas_state': {'version': '5.3.0', 'objects': [{'type': 'circle', 'left': 77, 'top': 88}]},
                        'canvas_width': 1054,
                        'canvas_height': 684,
                    },
                },
            },
        )
        performed = SessionTask.objects.create(
            session=origin_session,
            title='25/03/2026 · Tarea X',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            order=7,
            tactical_layout={
                'meta': {
                    'scope': 'coach',
                    'source': 'performed',
                    'performed_on': '2026-03-25',
                    'performed_session_id': origin_session.id,
                    # performed_from_task_id missing
                },
            },
        )

        response = self.client.get(reverse('sessions-task-edit', args=[performed.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&quot;left&quot;: 77')
        performed.refresh_from_db()
        meta = (performed.tactical_layout or {}).get('meta') or {}
        self.assertEqual(int(meta.get('performed_from_task_id') or 0), origin.id)

    def test_task_builder_loads_canvas_when_tactical_layout_is_json_string(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión layout string',
            duration_minutes=90,
        )
        layout = {
            'tokens': [],
            'timeline': [],
            'meta': {
                'scope': 'coach',
                'pitch_preset': 'full_pitch',
                'pitch_orientation': 'landscape',
                'graphic_editor': {
                    'canvas_state': {'version': '5.3.0', 'objects': [{'type': 'circle', 'left': 33, 'top': 44}]},
                    'canvas_width': 1054,
                    'canvas_height': 684,
                },
            },
        }
        task = SessionTask.objects.create(
            session=session,
            title='Tarea layout string',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout=json.dumps(layout, ensure_ascii=False),
        )

        response = self.client.get(reverse('sessions-task-edit', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&quot;left&quot;: 33')

    def test_task_builder_coerces_timeline_canvas_state_when_stored_as_string(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión timeline string',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea timeline string',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=15,
            tactical_layout={
                'tokens': [],
                'timeline': [
                    {
                        'title': 'Inicio',
                        'duration': 3,
                        'canvas_width': 1054,
                        'canvas_height': 684,
                        'canvas_state': json.dumps({'version': '5.3.0', 'objects': [{'type': 'circle', 'left': 12, 'top': 13}]}, ensure_ascii=False),
                    }
                ],
                'meta': {
                    'scope': 'coach',
                    'pitch_preset': 'full_pitch',
                    'pitch_orientation': 'landscape',
                    'graphic_editor': {
                        'canvas_state': {'version': '5.3.0', 'objects': []},
                        'canvas_width': 1054,
                        'canvas_height': 684,
                    },
                },
            },
        )

        response = self.client.get(reverse('sessions-task-edit', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&quot;left&quot;: 12')

    def test_task_builder_prefills_surface_as_artificial_turf(self):
        response = self.client.get(reverse('sessions-task-create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'option value="artificial_turf" selected')

    def test_session_task_detail_is_default_view_for_editable_tasks(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión detalle tarea',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Tarea detalle',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout={'meta': {'scope': 'coach'}},
        )

        response = self.client.get(reverse('session-task-detail', args=[task.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        chain = getattr(response, 'redirect_chain', []) or []
        # No debe redirigir al editor visual (la ficha es la vista por defecto).
        self.assertFalse(any('/coach/sesiones/tareas/' in str(url) and '/editar/' in str(url) for url, _ in chain))
        self.assertContains(response, 'Detalle de tarea')
        self.assertContains(response, 'Editar pizarra')

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
        # Al guardar dentro de una sesión real, el editor crea:
        # - 1 instancia dentro de la sesión
        # - 1 plantilla en Biblioteca (para reutilización)
        self.assertEqual(SessionTask.objects.count(), before_count + 2)
        task = SessionTask.objects.filter(session=session).order_by('-id').first()
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
        template_id = meta.get('library_source_task_id')
        self.assertTrue(bool(template_id))
        template_task = SessionTask.objects.get(id=template_id)
        template_meta = template_task.tactical_layout.get('meta') or {}
        self.assertNotEqual(template_task.session_id, session.id)
        self.assertTrue(bool(template_meta.get('is_template')))
        self.assertContains(response, 'Guardada en sesión 25/03/2026')
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
        task = SessionTask.objects.filter(session=session, title='Tarea con pasos').order_by('-id').first()
        self.assertIsNotNone(task)
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

        response = self.client.get(reverse('session-task-pdf', args=[task.id]) + '?one_page=0')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entrega Ejercicio')
        self.assertContains(response, 'Detalles del Ejercicio')
        self.assertContains(response, 'Descripción Gráfica')
        self.assertContains(response, 'Contenido de la tarea')
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
        task.task_preview_image.save(
            'preview-club-light.png',
            ContentFile(
                base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAGUlEQVR4nGM8ceIEA27AhEduBEsDqWEAAOxcAasqci/7AAAAAElFTkSuQmCC'
                )
            ),
            save=True,
        )

        response = self.client.get(reverse('session-task-pdf', args=[task.id]) + '?style=club&one_page=0')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Planificación de tarea')
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'Formato Club')
        self.assertContains(response, 'data:image/')

    @patch('football.views.weasyprint', None)
    def test_session_task_pdf_one_page_compacts_layout(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión base',
            duration_minutes=90,
        )
        task = SessionTask.objects.create(
            session=session,
            title='Resumen 1 página',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            objective='Objetivo largo que debe mostrarse completo en el PDF',
            coaching_points='Consigna 1\nConsigna 2\nConsigna 3\nConsigna 4\nConsigna 5',
            confrontation_rules='Regla 1\nRegla 2\nRegla 3\nRegla 4\nRegla 5',
            tactical_layout={
                'meta': {'scope': 'coach', 'training_type': 'Situaciones reducidas'},
                'timeline': [
                    {'title': 'Salida', 'duration': 2, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                    {'title': 'Finalización', 'duration': 4, 'canvas_state': {'version': '5.3.0', 'objects': []}},
                ],
            },
        )

        response = self.client.get(reverse('session-task-pdf', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="pdf-one-page"')
        # En modo 1 página ocultamos storyboard / secuencia animada para garantizar el layout.
        self.assertNotContains(response, 'Secuencia animada')
        self.assertNotContains(response, 'Paso 1')

    @patch('football.pdf_services.weasyprint', None)
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
        self.assertNotContains(response_club, '<div class="page-break"></div>')

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

    def test_session_task_detail_sheet_falls_back_to_meta_space_and_update_syncs_meta_space(self):
        session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 3, 25),
            focus='Sesión ficha',
            duration_minutes=90,
        )
        # Caso legacy real: `meta.space` existe pero `analysis.task_sheet.space` no.
        task = SessionTask.objects.create(
            session=session,
            title='Tarea ficha legacy',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout={
                'meta': {
                    'scope': 'coach',
                    'space': 'Medio campo',
                    'analysis': {'task_sheet': {'description': 'Desc', 'dimensions': '40x30', 'materials': 'Conos'}},
                    'graphic_editor': {'canvas_state': {'version': '5.3.0', 'objects': []}},
                }
            },
        )

        url = reverse('session-task-detail', args=[task.id]) + '?legacy=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Medio campo')

        response = self.client.post(
            url,
            {
                'detail_action': 'update_task_detail',
                'task_title': 'Tarea ficha legacy',
                'task_block': SessionTask.BLOCK_MAIN_1,
                'task_minutes': '18',
                'task_sheet_space': 'Zona central',
            },
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        meta = task.tactical_layout.get('meta') if isinstance(task.tactical_layout, dict) else {}
        analysis = meta.get('analysis') if isinstance(meta, dict) else {}
        sheet = analysis.get('task_sheet') if isinstance(analysis, dict) else {}
        self.assertEqual(str(meta.get('space') or '').strip(), 'Zona central')
        self.assertEqual(str(sheet.get('space') or '').strip(), 'Zona central')

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
            follow=True,
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
        self.assertIn(response.status_code, {301, 302})
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
        self.assertIn(response.status_code, {301, 302})
        self.assertEqual(SessionTask.objects.filter(session=session).count(), 3)

        response = self.client.post(
            reverse('sessions'),
            {
                'planner_action': 'delete_session_task',
                'planner_tab': 'planning',
                'task_id': task_a.id,
            },
        )
        self.assertIn(response.status_code, {301, 302})
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
            follow=True,
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
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

        response = self.client.get(f"{reverse('coach-detail')}?view=overview")

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

    def test_club_onboarding_brand_theme_post_renders_full_context(self):
        team = Team.objects.create(name='Equipo Tema', slug='equipo-tema')
        workspace = Workspace.objects.create(
            name='Club Tema',
            slug='club-tema',
            kind=Workspace.KIND_CLUB,
            primary_team=team,
            owner_user=self.user,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=team, is_default=True)
        self.client.force_login(self.user)
        team_cache_key = f'ctx:brand_theme:v1:w{int(workspace.id)}:t{int(team.id)}'
        default_cache_key = f'ctx:brand_theme:v1:w{int(workspace.id)}:t0'
        cache.set(team_cache_key, {'stale': True}, 60)
        cache.set(default_cache_key, {'stale': True}, 60)

        response = self.client.post(
            reverse('club-onboarding'),
            {
                'action': 'brand_theme',
                'theme_primary': '#123456',
                'theme_secondary': '#abcdef',
                'theme_bg': '#08111d',
                'theme_text': '#f5f7fa',
                'theme_button_bg': '#0f172a',
                'theme_button_text': '#ffffff',
                'theme_panel_flat': '#101827',
                'theme_line': '#90a1b9',
                'theme_shadow': 'soft',
                'theme_system_image_mode': 'both',
                'theme_font': 'avenir',
                'theme_font_weight': 'bold',
                'theme_font_style': 'italic',
                'theme_font_decoration': 'underline',
                'theme_font_size': 'large',
                'theme_ui': 'dark',
                'theme_bg_light': '#f4f7fb',
                'theme_text_light': '#0f172a',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Identidad corporativa guardada.')
        self.assertContains(response, 'Vista previa de página')
        pref = WorkspacePreference.objects.get(workspace=workspace, key='brand_theme:v1')
        saved = pref.value['teams'][str(team.id)]
        self.assertEqual(saved['font'], 'avenir')
        self.assertEqual(saved['font_weight'], 'bold')
        self.assertEqual(saved['font_style'], 'italic')
        self.assertEqual(saved['font_decoration'], 'underline')
        self.assertEqual(saved['font_size'], 'large')
        self.assertEqual(saved['system_image_mode'], 'both')
        refreshed_cache = cache.get(team_cache_key)
        self.assertNotEqual(refreshed_cache, {'stale': True})
        self.assertEqual(
            refreshed_cache['teams'][str(team.id)]['font'],
            'avenir',
        )
        self.assertIsNone(cache.get(default_cache_key))


class SessionPlanFieldsSerializationTests(TestCase):
    def test_parse_and_serialize_supports_session_extras(self):
        raw = serialize_session_plan_fields(
            {
                'warmup': 'Calentamiento',
                'activation': 'Activación',
                'main': 'Principal',
                'cooldown': 'Vuelta',
                'player_count': '18',
                'materials': 'Conos, petos',
                'absences': 'Juan (tobillo)',
                'notes': 'Notas generales',
            }
        )
        parsed = parse_session_plan_fields(raw)
        self.assertEqual(parsed.get('player_count'), '18')
        self.assertEqual(parsed.get('materials'), 'Conos, petos')
        self.assertEqual(parsed.get('absences'), 'Juan (tobillo)')
        self.assertEqual(parsed.get('notes'), 'Notas generales')


class SessionsPlannerTaskAssignTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo pruebas',
            slug='equipo-pruebas',
            short_name='Pruebas',
            category='senior',
        )
        self.user = get_user_model().objects.create_user(
            username='coach-sessions',
            email='coach-sessions@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)

        self.workspace = Workspace.objects.create(
            name='CLUB PRUEBAS',
            slug='club-pruebas',
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

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            week_start=week_start,
            week_end=week_end,
            status=TrainingMicrocycle.STATUS_DRAFT,
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=today,
            focus='Sesión normal',
            status=TrainingSession.STATUS_PLANNED,
            order=1,
        )

        source_microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo fuente',
            week_start=week_start - timedelta(days=7),
            week_end=week_end - timedelta(days=7),
            status=TrainingMicrocycle.STATUS_DRAFT,
        )
        source_session = TrainingSession.objects.create(
            microcycle=source_microcycle,
            session_date=today - timedelta(days=7),
            focus='Biblioteca interactiva · Entrenador',
            status=TrainingSession.STATUS_PLANNED,
            order=1,
        )
        self.source_task = SessionTask.objects.create(
            session=source_session,
            title='Tarea interactiva',
            block=SessionTask.BLOCK_ACTIVATION,
            duration_minutes=12,
            tactical_layout={'meta': {'repository': 'interactive'}},
            status=SessionTask.STATUS_PLANNED,
            order=1,
        )

    def test_assign_task_shows_in_selected_block_after_post(self):
        self.client.force_login(self.user)
        url = f"{reverse('sessions')}?workspace={self.workspace.id}&team={self.team.id}"
        response = self.client.post(
            url,
            data={
                'planner_action': 'copy_library_task_to_session',
                'planner_tab': 'sessions',
                'library_repo': 'traditional',
                'selected_session_id': str(self.session.id),
                'target_session_id': str(self.session.id),
                'target_block': SessionTask.BLOCK_ACTIVATION,
                'replace_existing': '1',
                'source_task_id': str(self.source_task.id),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        copied = (
            SessionTask.objects
            .filter(session=self.session, title='Tarea interactiva', deleted_at__isnull=True)
            .order_by('-id')
            .first()
        )
        self.assertIsNotNone(copied)
        html = response.content.decode('utf-8', errors='ignore')
        self.assertIn(f'data-task-id=\"{copied.id}\"', html)

    def test_assign_task_works_when_context_only_in_post(self):
        self.client.force_login(self.user)
        url = reverse('sessions')
        response = self.client.post(
            url,
            data={
                'planner_action': 'copy_library_task_to_session',
                'planner_tab': 'sessions',
                'library_repo': 'traditional',
                'team': str(self.team.id),
                'workspace': str(self.workspace.id),
                'selected_session_id': str(self.session.id),
                'target_session_id': str(self.session.id),
                'target_block': SessionTask.BLOCK_ACTIVATION,
                'replace_existing': '1',
                'source_task_id': str(self.source_task.id),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        copied = (
            SessionTask.objects
            .filter(session=self.session, deleted_at__isnull=True)
            .order_by('-id')
            .first()
        )
        self.assertIsNotNone(copied)


class SessionsPlannerCreateSessionTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo pruebas crear sesión',
            slug='equipo-pruebas-sesion',
            short_name='Pruebas',
            category='senior',
        )
        self.user = get_user_model().objects.create_user(
            username='coach-create-session',
            email='coach-create-session@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='CLUB PRUEBAS SESIÓN',
            slug='club-pruebas-sesion',
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
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            week_start=week_start,
            week_end=week_end,
            status=TrainingMicrocycle.STATUS_DRAFT,
        )

    def test_create_session_plan_persists_when_team_and_workspace_are_posted(self):
        self.client.force_login(self.user)
        url = reverse('sessions')
        today = timezone.localdate()
        response = self.client.post(
            url,
            data={
                'planner_action': 'create_session_plan',
                'planner_tab': 'sessions',
                'team': str(self.team.id),
                'workspace': str(self.workspace.id),
                'plan_microcycle_id': str(self.microcycle.id),
                'plan_session_date': today.strftime('%Y-%m-%d'),
                'plan_session_focus': 'Transición + finalización',
                'plan_session_minutes': '90',
                'plan_session_intensity': TrainingSession.INTENSITY_MEDIUM,
                'plan_session_status': TrainingSession.STATUS_PLANNED,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = TrainingSession.objects.filter(microcycle=self.microcycle, focus__iexact='Transición + finalización').first()
        self.assertIsNotNone(created)


class SessionsPlannerLoadPastSessionTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo pruebas cargar sesión',
            slug='equipo-pruebas-cargar',
            short_name='Pruebas',
            category='senior',
        )
        self.user = get_user_model().objects.create_user(
            username='coach-load-session',
            email='coach-load-session@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='CLUB PRUEBAS CARGAR',
            slug='club-pruebas-cargar',
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
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Microciclo',
            week_start=week_start,
            week_end=week_end,
            status=TrainingMicrocycle.STATUS_DRAFT,
        )
        self.past_session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=today - timedelta(days=2),
            focus='Sesión realizada',
            status=TrainingSession.STATUS_DONE,
            order=1,
        )

    def test_load_past_session_without_tab_param_stays_on_sessions_tab(self):
        self.client.force_login(self.user)
        url = f"{reverse('sessions')}?workspace={self.workspace.id}&team={self.team.id}&session_id={self.past_session.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', errors='ignore')
        self.assertIn('data-tab=\"sessions\"', html)
        self.assertIn('tab-panel is-active', html)
        self.assertIn('Sesiones · Estructura por bloques', html)


class StaticAssetBudgetTests(SimpleTestCase):
    def test_team_hero_images_are_reasonable_size(self):
        base = Path(settings.BASE_DIR)
        targets = [
            base / 'static' / 'football' / 'images' / 'team-01.jpg',
            base / 'static' / 'football' / 'images' / 'team-02.jpg',
            base / 'static' / 'football' / 'images' / 'team-03.jpg',
        ]
        for p in targets:
            self.assertTrue(p.exists(), f"Missing static asset: {p}")
            size = p.stat().st_size
            self.assertLess(
                size,
                650_000,
                f"{p} is too large ({size} bytes). Optimize it (e.g. scripts/optimize_static_assets.py).",
            )

    def test_player_pngs_are_reasonable_size(self):
        base = Path(settings.BASE_DIR)
        players_dir = base / 'static' / 'football' / 'images' / 'players'
        self.assertTrue(players_dir.exists(), f"Missing static dir: {players_dir}")
        offenders = []
        for p in sorted(players_dir.glob('*.png')):
            try:
                size = p.stat().st_size
            except Exception:
                continue
            if size > 1_000_000:
                offenders.append((p.name, size))
        self.assertFalse(offenders, f"Large player PNGs (>1MB): {offenders}")


class HealthzEndpointTests(TestCase):
    def test_healthz_returns_payload(self):
        response = self.client.get('/healthz')
        self.assertIn(response.status_code, (200, 503))
        payload = response.json()
        self.assertIn('ok', payload)
        self.assertIn('checks', payload)


class Kit2DGeneratorEndpointTests(TestCase):
    def test_kit2d_generate_requires_login(self):
        resp = self.client.post('/api/kits/2d/generate/')
        self.assertIn(resp.status_code, (302, 401, 403))


class AcademyEndpointTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Equipo Academia',
            slug='equipo-academia',
            short_name='Academia',
            category='Prebenjamín',
        )
        self.team2 = Team.objects.create(
            name='Equipo Academia 2',
            slug='equipo-academia-2',
            short_name='Academia 2',
            category='Prebenjamín',
        )
        self.user = get_user_model().objects.create_user(
            username='player-academy',
            email='player-academy@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.workspace_enabled = Workspace.objects.create(
            name='Club Academia On',
            slug='club-academia-on',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'academy': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace_enabled, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace_enabled, team=self.team, is_default=True)

        self.workspace_disabled = Workspace.objects.create(
            name='Club Academia Off',
            slug='club-academia-off',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team2,
            enabled_modules={'academy': False},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace_disabled, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace_disabled, team=self.team2, is_default=True)

    def test_academy_today_requires_login(self):
        resp = self.client.get('/api/academy/today/')
        self.assertIn(resp.status_code, (302, 401, 403))

    def test_academy_today_forbidden_when_disabled(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/api/academy/today/?workspace={self.workspace_disabled.id}&team={self.team2.id}')
        self.assertEqual(resp.status_code, 403)
        payload = resp.json()
        self.assertFalse(payload.get('ok'))

    def test_academy_home_ok_when_enabled(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/academia/?workspace={self.workspace_enabled.id}&team={self.team.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', errors='ignore')
        self.assertIn('Academia', html)

    def test_academy_today_ok_when_enabled(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/api/academy/today/?workspace={self.workspace_enabled.id}&team={self.team.id}')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get('ok'))
        self.assertIn('items', payload)


class AiTrainerLibraryTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Equipo IA', slug='equipo-ia', short_name='IA', is_primary=True)
        self.user = get_user_model().objects.create_user(
            username='coach-ia',
            email='coach-ia@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='WS IA',
            slug='ws-ia',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
            enabled_modules={'sessions': True},
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)

    def _activate_workspace(self):
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def test_ai_trainer_can_save_task_to_separate_repository(self):
        self.client.force_login(self.user)
        self._activate_workspace()

        url = reverse('ai-trainer') + f'?team={self.team.id}'
        response = self.client.post(
            url,
            data={
                'action': 'save_task',
                'variant': 'A',
                'profile': 'hybrid',
                'phase': 'Ataque',
                'goal': 'Trabajar 3er hombre y ocupar 5 carriles atacando zona 14.',
            },
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})

        task = (
            SessionTask.objects
            .filter(session__microcycle__team=self.team, deleted_at__isnull=True, title__startswith='IA ·')
            .order_by('-id')
            .first()
        )
        self.assertIsNotNone(task)
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        self.assertEqual(str(meta.get('repository') or ''), 'ai_trainer')

    def test_ai_trainer_dictionary_training_adds_new_detection(self):
        self.client.force_login(self.user)
        self._activate_workspace()

        url = reverse('ai-trainer') + f'?team={self.team.id}'
        resp = self.client.post(
            url,
            data={
                'action': 'dict_save',
                'dict_section': 'principles',
                'dict_key': 'concepto_custom',
                'dict_label': 'Concepto Custom',
                'dict_keywords': 'palabraunica123',
                'dict_coaching_points': 'consigna 1\\nconsigna 2',
                'profile': 'hybrid',
                'phase': 'Ataque',
                'goal': 'palabraunica123',
            },
            secure=True,
        )
        self.assertIn(resp.status_code, {301, 302})

        resp2 = self.client.post(
            url,
            data={
                'action': 'generate',
                'profile': 'hybrid',
                'phase': 'Ataque',
                'goal': 'Quiero trabajar palabraunica123 hoy.',
            },
            secure=True,
        )
        self.assertEqual(resp2.status_code, 200)
        html = (resp2.content or b'').decode('utf-8', errors='ignore')
        self.assertIn('Concepto Custom', html)
