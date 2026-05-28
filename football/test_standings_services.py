from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from football import standings_services
from football.models import (
    Competition,
    Group,
    Season,
    Team,
    TeamStanding,
    WorkspaceCompetitionContext,
)


class StandingsServicesTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='Liga Standings', slug='liga-standings')
        self.season = Season.objects.create(competition=competition, name='2026/2027')
        self.group = Group.objects.create(season=self.season, name='Grupo Standings', slug='grupo-standings')
        self.team = Team.objects.create(
            name='Equipo Standings',
            slug='equipo-standings',
            group=self.group,
            is_primary=True,
        )
        self.rival = Team.objects.create(name='Rival Standings', slug='rival-standings', group=self.group)

    def test_serialize_standings_orders_database_rows(self):
        TeamStanding.objects.create(
            season=self.season,
            group=self.group,
            team=self.rival,
            position=2,
            played=4,
            wins=2,
            draws=1,
            losses=1,
            goals_for=8,
            goals_against=5,
            goal_difference=3,
            points=7,
        )
        TeamStanding.objects.create(
            season=self.season,
            group=self.group,
            team=self.team,
            position=1,
            played=4,
            wins=3,
            draws=1,
            losses=0,
            goals_for=10,
            goals_against=2,
            goal_difference=8,
            points=10,
        )

        rows = standings_services.serialize_standings(self.group)

        self.assertEqual([row['team'] for row in rows], ['EQUIPO STANDINGS', 'RIVAL STANDINGS'])
        self.assertEqual(rows[0]['points'], 10)

    def test_resolve_standings_for_universo_non_primary_uses_database(self):
        self.team.is_primary = False
        self.team.save(update_fields=['is_primary'])
        TeamStanding.objects.create(
            season=self.season,
            group=self.group,
            team=self.team,
            position=1,
            points=12,
        )
        snapshot = {
            'standings': [
                {'position': 1, 'team': 'OTRO EQUIPO', 'points': 99},
            ]
        }

        rows = standings_services.resolve_standings_for_team(
            self.team,
            snapshot=snapshot,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
        )

        self.assertEqual(rows[0]['team'], 'EQUIPO STANDINGS')
        self.assertEqual(rows[0]['points'], 12)

    def test_latest_standings_group_prefers_recent_team_standing(self):
        other_group = Group.objects.create(
            season=self.season,
            name='Grupo Standings',
            slug='grupo-standings-2',
        )
        old_time = timezone.now() - timedelta(days=2)
        new_time = timezone.now()
        TeamStanding.objects.create(
            season=self.season,
            group=self.group,
            team=self.team,
            position=1,
            points=9,
            last_updated=old_time,
        )
        TeamStanding.objects.create(
            season=self.season,
            group=other_group,
            team=self.team,
            position=1,
            points=15,
            last_updated=new_time,
        )

        group = standings_services.latest_standings_group_for_team(self.team)

        self.assertEqual(group, other_group)

    def test_universo_snapshot_support_requires_legacy_primary_match(self):
        snapshot = {'standings': [{'team': 'Equipo Standings'}]}

        with patch('football.standings_services.single_club_fallback_enabled', return_value=True):
            self.assertTrue(standings_services.universo_snapshot_supports_team(snapshot, self.team))

        self.team.is_primary = False
        self.team.save(update_fields=['is_primary'])
        with patch('football.standings_services.single_club_fallback_enabled', return_value=True):
            self.assertFalse(standings_services.universo_snapshot_supports_team(snapshot, self.team))
