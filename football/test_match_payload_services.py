from datetime import date, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from football import match_payload_services
from football.models import Competition, Group, Match, Season, Team


class MatchPayloadServicesTests(SimpleTestCase):
    def test_normalize_next_match_payload_accepts_string_opponent(self):
        payload = match_payload_services.normalize_next_match_payload({'opponent': 'Rival FC'})

        self.assertEqual(payload['opponent']['name'], 'Rival FC')
        self.assertEqual(payload['opponent']['full_name'], 'Rival FC')
        self.assertEqual(payload['opponent']['team_code'], '')

    def test_parse_payload_date_accepts_supported_formats(self):
        self.assertEqual(match_payload_services.parse_payload_date('2026-05-27'), date(2026, 5, 27))
        self.assertEqual(match_payload_services.parse_payload_date('27/05/2026'), date(2026, 5, 27))
        self.assertIsNone(match_payload_services.parse_payload_date('bad-date'))

    def test_build_match_payload_marks_home_status(self):
        home = SimpleNamespace(name='Casa')
        away = SimpleNamespace(name='Rival')
        match = SimpleNamespace(
            home_team=home,
            away_team=away,
            round='J1',
            date=date(2026, 5, 27),
            location='Campo',
        )

        payload = match_payload_services.build_match_payload(match, home, status='next')

        self.assertTrue(payload['home'])
        self.assertEqual(payload['opponent']['name'], 'Rival')
        self.assertEqual(payload['date'], '2026-05-27')


class WorkspaceSchedulePayloadTests(TestCase):
    def test_build_workspace_schedule_payload_orders_and_marks_status(self):
        competition = Competition.objects.create(name='Liga Payload', slug='liga-payload')
        season = Season.objects.create(competition=competition, name='2026/2027')
        group = Group.objects.create(season=season, name='Grupo Payload', slug='grupo-payload')
        team = Team.objects.create(name='Casa', slug='casa', group=group)
        rival = Team.objects.create(name='Rival', slug='rival', group=group)
        today = timezone.localdate()
        Match.objects.create(season=season, group=group, home_team=team, away_team=rival, date=today, round='J1', location='Campo')

        payload = match_payload_services.build_workspace_schedule_payload(team)

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['status'], 'next')
        self.assertEqual(payload[0]['opponent']['name'], 'Rival')

    def test_build_local_next_match_payload_falls_back_to_latest_match(self):
        competition = Competition.objects.create(name='Liga Local', slug='liga-local')
        season = Season.objects.create(competition=competition, name='2026/2027')
        group = Group.objects.create(season=season, name='Grupo Local', slug='grupo-local')
        team = Team.objects.create(name='Casa Local', slug='casa-local', group=group)
        rival = Team.objects.create(name='Rival Local', slug='rival-local', group=group)
        yesterday = timezone.localdate() - timedelta(days=1)
        Match.objects.create(season=season, group=group, home_team=rival, away_team=team, date=yesterday, round='J0', location='Campo')

        payload = match_payload_services.build_local_next_match_payload(team)

        self.assertEqual(payload['status'], 'next')
        self.assertFalse(payload['home'])
        self.assertEqual(payload['opponent']['name'], 'Rival Local')

    def test_next_match_payload_is_usable_rejects_missing_round_or_placeholder_opponent(self):
        self.assertFalse(match_payload_services.next_match_payload_is_usable({'status': 'next', 'opponent': 'Rival FC'}))
        self.assertFalse(match_payload_services.next_match_payload_is_usable({'status': 'next', 'round': 'J1', 'opponent': 'Rival por confirmar'}))
        self.assertTrue(match_payload_services.next_match_payload_is_usable({'status': 'next', 'round': 'J1', 'opponent': 'Rival FC'}))
