from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from football import match_payload_services


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
