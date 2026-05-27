from datetime import date
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
