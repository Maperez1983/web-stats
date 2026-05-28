from datetime import time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from football import next_match_services
from football.models import Competition, ConvocationRecord, Group, Match, Season, Team


class NextMatchServicesTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Next', slug='liga-next')
        self.season = Season.objects.create(competition=competition, name='2026/2027')
        self.group = Group.objects.create(season=self.season, name='Grupo Next', slug='grupo-next')
        self.team = Team.objects.create(name='Equipo Next', slug='equipo-next', group=self.group)
        self.rival = Team.objects.create(name='Rival Next', slug='rival-next', group=self.group)

    def test_build_universo_standings_lookup_normalizes_keys(self):
        lookup = next_match_services.build_universo_standings_lookup(
            {
                'standings': [
                    {
                        'team': 'Rival Next',
                        'full_name': 'Rival Next C.F.',
                        'crest_url': '/crest.png',
                        'team_code': '222',
                    }
                ]
            }
        )

        self.assertEqual(lookup['rivalnext']['full_name'], 'Rival Next C.F.')
        self.assertEqual(lookup['rivalnext']['team_code'], '222')

    def test_resolve_rival_identity_prefers_matching_snapshot_metadata(self):
        with patch(
            'football.next_match_services.load_universo_snapshot',
            return_value={'standings': [{'team': 'Rival Next', 'full_name': 'Rival Next C.F.'}]},
        ):
            full_name, _crest = next_match_services.resolve_rival_identity('Rival Next')

        self.assertEqual(full_name, 'Rival Next C.F.')

    def test_build_next_match_from_convocation_normalizes_future_record(self):
        match_date = timezone.localdate() + timedelta(days=5)
        match = Match.objects.create(
            season=self.season,
            group=self.group,
            round='J12',
            date=match_date,
            location='Campo Next',
            home_team=self.rival,
            away_team=self.team,
        )
        ConvocationRecord.objects.create(
            team=self.team,
            match=match,
            round='J12',
            match_date=match_date,
            match_time=time(17, 30),
            location='Campo Next',
            opponent_name='Rival Next',
            is_current=True,
        )

        payload = next_match_services.build_next_match_from_convocation(self.team)

        self.assertEqual(payload['round'], 'J12')
        self.assertEqual(payload['date'], match_date.isoformat())
        self.assertEqual(payload['time'], '17:30')
        self.assertEqual(payload['opponent']['name'], 'Rival Next')
        self.assertFalse(payload['home'])
        self.assertEqual(payload['source'], 'convocation-manual')

    def test_build_next_match_from_convocation_ignores_past_record(self):
        ConvocationRecord.objects.create(
            team=self.team,
            round='J1',
            match_date=timezone.localdate() - timedelta(days=1),
            opponent_name='Rival Next',
            is_current=True,
        )

        payload = next_match_services.build_next_match_from_convocation(self.team)

        self.assertIsNone(payload)
