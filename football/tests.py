import base64
import json
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import AnalystVideoFolder, Competition, ConvocationRecord, Group, Match, MatchEvent, Player, PlayerCommunication, PlayerFine, PlayerStatistic, RivalAnalysisReport, RivalVideo, Season, SessionTask, Team, TeamStanding, TrainingMicrocycle, TrainingSession, UserInvitation
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
from football.query_helpers import get_active_injury_player_ids, get_current_convocation_record, is_injury_record_active, is_manual_sanction_active
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
        self.client.force_login(self.user)
        cache.set(SCRAPE_LOCK_KEY, '1', timeout=60)
        response = self.client.post(reverse('dashboard-refresh'))
        self.assertEqual(response.status_code, 429)
        cache.delete(SCRAPE_LOCK_KEY)

    def test_dashboard_page_requires_login(self):
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

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

        self.assertEqual(response.status_code, 200)
        self.invitation.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.invitation.is_active)
        self.assertIsNotNone(self.invitation.accepted_at)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password('NuevaPassSegura2026!'))


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
        self.assertContains(response, '76.50 kg')
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
                self.assertTrue(
                    response.context['player_photo_url'].endswith(f'/media-test/player-photos/player-{self.player.id}.png')
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


class AdminUsersTests(TestCase):
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

    def test_user_update_keeps_edited_user_visible_and_focused(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin-page'),
            {
                'form_action': 'user_update',
                'active_tab': 'users',
                'users_segment': 'all',
                'user_id': self.beta.id,
                'full_name': 'Beta Nuevo',
                'username': 'omega-user',
                'email': 'omega@example.com',
                'password': '',
                'role': AppUserRole.ROLE_PLAYER,
            },
            follow=True,
        )

        self.beta.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.beta.username, 'omega-user')
        self.assertEqual(self.beta.get_full_name(), 'Beta Nuevo')
        self.assertEqual(response.context['focus_user_id'], self.beta.id)
        self.assertEqual(response.context['users_filtered'][0].id, self.beta.id)
        self.assertContains(response, f'id="user-{self.beta.id}"')
        self.assertContains(response, 'value="omega-user"')

    def test_user_update_switches_to_all_segment_when_role_changes_out_of_filter(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin-page'),
            {
                'form_action': 'user_update',
                'active_tab': 'users',
                'users_segment': 'players',
                'user_id': self.beta.id,
                'full_name': 'Beta Analista',
                'username': 'beta-analista',
                'email': 'beta-analista@example.com',
                'password': '',
                'role': AppUserRole.ROLE_ANALYST,
            },
            follow=True,
        )

        self.beta.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.beta.username, 'beta-analista')
        self.assertEqual(self.beta.app_role.role, AppUserRole.ROLE_ANALYST)
        self.assertEqual(response.context['users_segment'], 'all')
        self.assertEqual(response.context['users_filtered'][0].id, self.beta.id)


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
        response = self.client.get(reverse('player-dashboard'), {'match': self.match.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival View')
        self.assertContains(response, 'Acciones totales:')
        mocked_refresh.assert_called_once_with(self.team, force=False)

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
        self.assertContains(response, 'Ya existe una sesión con la misma fecha y foco en este microciclo.')
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
                }
            },
        )

        response = self.client.get(reverse('session-task-pdf', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tarea Entrenamiento')
        self.assertContains(response, 'Ficha Técnica')
        self.assertContains(response, 'Descripción Gráfica')
        self.assertContains(response, 'Consigna / Explicación')
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
        self.assertContains(response, 'Tarea Entrenamiento')
        self.assertFalse(SessionTask.objects.filter(title='Borrador sin guardar').exists())

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
        self.assertFalse(SessionTask.objects.filter(id=task_a.id).exists())

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
        self.rival_future = Team.objects.create(name='Rival Futuro', slug='rival-futuro', group=self.group)
        self.rival_old = Team.objects.create(name='Rival Antiguo', slug='rival-antiguo', group=self.group)
        self.client.force_login(self.user)

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_prefers_real_upcoming_match_over_past_convocation(self, _mock_next):
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
            round='J23',
            match_date=date(2026, 3, 22),
            location='Pasado',
            opponent_name='Rival Antiguo',
            is_current=True,
        )

        response = self.client.get(reverse('coach-detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rival Futuro')
        self.assertNotContains(response, 'Rival Antiguo')
        self.assertContains(response, 'Próximo Partido')

    @patch('football.views.load_preferred_next_match_payload', return_value=None)
    def test_coach_overview_renders_manual_rival_report_summary(self, _mock_next):
        Match.objects.create(
            season=self.group.season,
            group=self.group,
            round='J24',
            date=date(2026, 3, 29),
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
        self.assertContains(response, 'Informe previo J24')
        self.assertContains(response, 'Sufren cuando les obligas a defender amplitud.')
        self.assertContains(response, 'Staff Técnico')

    def test_coach_cards_page_groups_modules_by_function(self):
        response = self.client.get(reverse('coach-cards'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plantilla técnica')
        self.assertContains(response, 'Datos temporada')
        self.assertContains(response, 'Sesiones')
        self.assertContains(response, 'Convocatoria y 11 inicial')
        self.assertContains(response, 'Análisis')
        self.assertNotContains(response, '>Entrenador<', html=False)
        self.assertContains(response, reverse('sessions-goalkeeper'))
        self.assertContains(response, reverse('sessions-fitness'))
        self.assertContains(response, reverse('convocation'))
        self.assertContains(response, reverse('initial-eleven'))
