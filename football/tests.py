from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import AnalystVideoFolder, Competition, ConvocationRecord, Group, Match, MatchEvent, Player, PlayerStatistic, RivalVideo, Season, Team, TeamStanding, UserInvitation
from football.bootstrap import ensure_bootstrap_admin_from_env
from football.event_taxonomy import (
    PASS_KEYWORDS,
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


class CoachTrainerMetricsTests(TestCase):
    def setUp(self):
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
        response = self.client.get(reverse('coach-role-trainer'), {'player': self.player.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn('coach_player_view', response.context)
        self.assertEqual(response.context['coach_player_view']['mode'], 'season')

        response = self.client.get(
            reverse('coach-role-trainer'),
            {'player': self.player.id, 'player_match': self.match.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['coach_player_view']['mode'], 'match')


class AnalysisVideoWorkspaceTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Analista', slug='liga-analista', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Analista', slug='grupo-analista')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-analista', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Analista', slug='rival-analista', group=group)
        self.player = Player.objects.create(team=self.team, name='Ivan', position='DC')

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
