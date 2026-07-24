from django.contrib.auth import get_user_model
from django.test import TestCase

from football.models import (
    CoachPitchBoardLayout,
    Player,
    Team,
    Workspace,
    WorkspaceSeason,
    WorkspaceSeasonPlayer,
)


class CoachPitchBoardPersistenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('pb', 'pb@example.com', 'x')
        self.team = Team.objects.create(name='Bena', slug='bena', is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Bena', slug='bena', kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        season = WorkspaceSeason.objects.create(
            workspace=self.workspace, label='2026/2027', start_date='2026-07-01', is_active=True
        )
        self.workspace.active_season = season
        self.workspace.save()
        self.player = Player.objects.create(team=self.team, name='Nico', position='Pivote', number=6, is_active=True)
        WorkspaceSeasonPlayer.objects.create(season=season, player=self.player, is_confirmed=True)
        self.client.force_login(self.user)
        s = self.client.session
        s['active_workspace_id'] = self.workspace.id
        s.save()

    def _save(self, **data):
        return self.client.post('/coach/plantilla/pizarra/guardar/', data, HTTP_HOST='localhost')

    def test_save_persists_position_shared(self):
        resp = self._save(team_id=self.team.id, player_id=self.player.id, left='33.3', top='44.4')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        layout = CoachPitchBoardLayout.objects.get(team=self.team)
        self.assertEqual(layout.positions, {str(self.player.id): [33.3, 44.4]})
        self.assertEqual(layout.updated_by_id, self.user.id)

    def test_home_renders_saved_position(self):
        CoachPitchBoardLayout.objects.create(team=self.team, positions={str(self.player.id): [55.5, 66.6]})
        resp = self.client.get(f'/coach/?team={self.team.id}', HTTP_HOST='localhost')
        body = resp.content.decode('utf-8', 'ignore')
        # Debe salir con punto decimal (CSS válido), no coma localizada.
        self.assertIn('left:55.5%;top:66.6%;', body)

    def test_player_from_other_team_is_rejected(self):
        other = Team.objects.create(name='Otro', slug='otro')
        stranger = Player.objects.create(team=other, name='X', is_active=True)
        resp = self._save(team_id=self.team.id, player_id=stranger.id, left='10', top='10')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(CoachPitchBoardLayout.objects.filter(team=self.team).exists())

    def test_reset_clears_positions(self):
        CoachPitchBoardLayout.objects.create(team=self.team, positions={str(self.player.id): [10.0, 10.0]})
        resp = self._save(team_id=self.team.id, reset='1')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('reset'))
        self.assertEqual(CoachPitchBoardLayout.objects.get(team=self.team).positions, {})

    def test_out_of_range_is_clamped(self):
        self._save(team_id=self.team.id, player_id=self.player.id, left='250', top='-40')
        pos = CoachPitchBoardLayout.objects.get(team=self.team).positions[str(self.player.id)]
        self.assertLessEqual(pos[0], 98.0)
        self.assertGreaterEqual(pos[1], 4.0)
