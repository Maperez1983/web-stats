from unittest.mock import patch

from django.test import TestCase

from football import stats_services
from football.dashboard_services import (
    compute_player_cards_for_match,
    compute_player_metrics,
    compute_team_metrics_for_match,
)
from football.models import (
    Competition,
    Group,
    Match,
    MatchEvent,
    Player,
    PlayerEvaluation,
    PlayerSeasonReport,
    Season,
    Team,
)


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


class PlayerCardStaffRatingTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Cards', slug='liga-cards', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Cards', slug='grupo-cards')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-cards', group=group, is_primary=True)

    def _mock_dashboard_row(self, player):
        return {
            'player_id': player.id,
            'name': player.name,
            'number': player.number,
            'photo_url': '',
            'pj': 1,
            'minutes': 90,
            'goals': 0,
            'assists': 0,
            'total_actions': 12,
            'success_rate': 75,
        }

    @patch('football.dashboard_services.compute_player_dashboard')
    def test_player_cards_include_staff_season_report_average(self, mock_dashboard):
        player = Player.objects.create(team=self.team, name='Javi Cazorla', number=8, position='MC')
        mock_dashboard.return_value = [self._mock_dashboard_row(player)]
        PlayerSeasonReport.objects.create(
            team=self.team,
            player=player,
            technical_rating=8,
            tactical_rating=6,
        )

        cards = stats_services.compute_player_cards(self.team)

        self.assertEqual(cards[0]['staff_rating_average'], 7.0)
        self.assertEqual(cards[0]['staff_rating_display'], '7/10')
        self.assertEqual(cards[0]['staff_rating_source'], 'Informe staff')

    @patch('football.dashboard_services.compute_player_dashboard')
    def test_player_cards_fallback_to_closed_staff_evaluation(self, mock_dashboard):
        player = Player.objects.create(team=self.team, name='Mario Perez', number=10, position='MP')
        mock_dashboard.return_value = [self._mock_dashboard_row(player)]
        PlayerEvaluation.objects.create(
            team=self.team,
            player=player,
            status=PlayerEvaluation.STATUS_CLOSED,
            technical_rating=9,
            tactical_rating=7,
            physical_rating=8,
        )

        cards = stats_services.compute_player_cards(self.team)

        self.assertEqual(cards[0]['staff_rating_average'], 8.0)
        self.assertEqual(cards[0]['staff_rating_display'], '8/10')
        self.assertEqual(cards[0]['staff_rating_source'], 'Evaluación staff')
