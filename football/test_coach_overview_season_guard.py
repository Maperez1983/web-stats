from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from football.competition_season_services import current_season_name
from football.models import (
    Competition,
    Group,
    Match,
    Season,
    Team,
    TeamStanding,
    Workspace,
    WorkspaceTeam,
)


class CoachOverviewSeasonGuardTests(TestCase):
    """La portada no debe mostrar clasificación ni próximo rival de una temporada ya cerrada."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser('guard', 'guard@example.com', 'x')
        self.competition = Competition.objects.create(name='División Honor Andaluza', slug='dha')

    def _client_for(self, team, workspace):
        client = self.client
        client.force_login(self.user)
        session = client.session
        session['active_workspace_id'] = workspace.id
        session.save()
        return client

    def _build(self, season_name, *, is_current, match_days_from_today, points, played):
        season = Season.objects.create(competition=self.competition, name=season_name, is_current=is_current)
        group = Group.objects.create(season=season, name='Grupo 2', slug=f'g2-{season_name.replace("/", "-")}')
        team = Team.objects.create(name='C.D. Benagalbón', slug='cd-bena', group=group, is_primary=True)
        rival = Team.objects.create(name='Cuevas C.F.', slug='cuevas', group=group)
        for i, t in enumerate((team, rival), 1):
            TeamStanding.objects.create(season=season, group=group, team=t, position=i, points=points, played=played)
        Match.objects.create(
            home_team=team, away_team=rival, group=group, season=season, round='Jornada X',
            date=timezone.localdate() + timedelta(days=match_days_from_today),
        )
        workspace = Workspace.objects.create(
            name='Bena', slug='bena', kind=Workspace.KIND_CLUB, primary_team=team
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=team, is_default=True)
        return team, workspace

    def test_past_season_data_is_suppressed(self):
        # Grupo del equipo en una temporada anterior; partido "próximo" en el pasado.
        team, workspace = self._build('2019/2020', is_current=False, match_days_from_today=-90, points=55, played=55)
        resp = self._client_for(team, workspace).get(f'/coach/?team={team.id}', HTTP_HOST='localhost')
        body = resp.content.decode('utf-8', 'ignore')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('Aún no hay clasificación', body)  # estado de pretemporada
        self.assertNotIn('Jornada X', body)  # el partido viejo no se pinta como próximo
        self.assertIn('Rival por confirmar', body)

    def test_current_season_data_is_shown(self):
        # Temporada vigente aunque sea pretemporada (PJ=0): debe mostrarse.
        team, workspace = self._build(current_season_name(), is_current=True, match_days_from_today=15, points=0, played=0)
        resp = self._client_for(team, workspace).get(f'/coach/?team={team.id}', HTTP_HOST='localhost')
        body = resp.content.decode('utf-8', 'ignore')

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Aún no hay clasificación', body)
        self.assertIn('standings-table', body)
        self.assertIn('Cuevas C.F.', body)  # próximo rival real
