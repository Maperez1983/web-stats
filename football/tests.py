from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import Competition, ConvocationRecord, Group, Match, Player, PlayerStatistic, Season, Team, UserInvitation
from football.bootstrap import ensure_bootstrap_admin_from_env
from football.healthchecks import run_system_healthcheck
from football.manual_stats import get_manual_player_base_overrides, save_manual_player_base_overrides, season_display_name
from football.query_helpers import get_current_convocation_record, is_manual_sanction_active
from football.models import AppUserRole
from football.services import find_roster_entry
from football.staff_briefing import build_weekly_staff_brief
from football.task_library import filter_task_library, prepare_task_library
from football.views import SCRAPE_LOCK_KEY
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
