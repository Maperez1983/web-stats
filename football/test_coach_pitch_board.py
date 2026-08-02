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

    def test_home_and_roster_render_interactive_status_filters(self):
        for url in (f'/coach/?team={self.team.id}', f'/coach/plantilla/?team={self.team.id}'):
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_HOST='localhost')
                self.assertEqual(response.status_code, 200)
                body = response.content.decode('utf-8', 'ignore')
                self.assertIn('aria-label="Filtrar jugadores por estado"', body)
                self.assertIn('data-pb-filter="all"', body)
                self.assertIn('data-pb-filter="available"', body)
                self.assertIn('data-pb-filter="trial"', body)
                self.assertIn('data-pb-filter="injured"', body)
                self.assertIn('data-pb-state="available"', body)

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

    def test_baja_drops_saved_position(self):
        from football.season_history_services import mark_player_left_current_season

        other = Player.objects.create(team=self.team, name='Otro', position='Central', number=4, is_active=True)
        WorkspaceSeasonPlayer.objects.create(
            season=self.workspace.active_season, player=other, team=self.team,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        CoachPitchBoardLayout.objects.create(
            team=self.team, positions={str(self.player.id): [30.0, 40.0], str(other.id): [70.0, 80.0]}
        )
        mark_player_left_current_season(self.workspace.active_season, other)
        positions = CoachPitchBoardLayout.objects.get(team=self.team).positions
        self.assertNotIn(str(other.id), positions)  # su posición se borró
        self.assertIn(str(self.player.id), positions)  # el resto intacto

    def test_out_of_range_is_clamped(self):
        self._save(team_id=self.team.id, player_id=self.player.id, left='250', top='-40')
        pos = CoachPitchBoardLayout.objects.get(team=self.team).positions[str(self.player.id)]
        self.assertLessEqual(pos[0], 98.0)
        self.assertGreaterEqual(pos[1], 4.0)

    def test_scouted_player_persists(self):
        """El bug que veía el usuario: los ojeados ("A prueba", chips scout-N) se podían arrastrar en
        la pizarra de la home pero su posición NO se guardaba (el JS no hacía POST y el endpoint no
        aceptaba ids no numéricos) -> al recargar volvían a su sitio. Ahora persisten bajo clave scout-N."""
        from football.models import ScoutingTarget

        target = ScoutingTarget.objects.create(
            workspace=self.workspace, subject_name='Enrique', position='LI',
            available_for_coach_tools=True, status=ScoutingTarget.STATUS_WATCH if hasattr(ScoutingTarget, 'STATUS_WATCH') else 'watch',
        )
        resp = self._save(team_id=self.team.id, player_id=f'scout-{target.id}', left='18.0', top='74.0')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        layout = CoachPitchBoardLayout.objects.get(team=self.team)
        self.assertEqual(layout.positions.get(f'scout-{target.id}'), [18.0, 74.0])
        # Y el loader devuelve la posición bajo la clave string (no la descarta como antes).
        from football.views import _coach_pitch_board_positions
        loaded = _coach_pitch_board_positions(self.team)
        self.assertEqual(loaded.get(f'scout-{target.id}'), [18.0, 74.0])

    def test_scouted_player_of_other_workspace_rejected(self):
        """Guardrail: no se puede guardar la posición de un ojeado que no es de este workspace."""
        from football.models import ScoutingTarget, Workspace, Team

        other_team = Team.objects.create(name='Otro Club', slug='otro-club')
        other_ws = Workspace.objects.create(name='Otro', slug='otro-ws', kind=Workspace.KIND_CLUB, primary_team=other_team)
        stranger = ScoutingTarget.objects.create(workspace=other_ws, subject_name='Ajeno', position='DC', available_for_coach_tools=True)
        resp = self._save(team_id=self.team.id, player_id=f'scout-{stranger.id}', left='40', top='40')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(CoachPitchBoardLayout.objects.filter(team=self.team).exists())

    def test_shared_identity_player_persists(self):
        """Regresión: un jugador presente en el equipo SOLO por membresía de temporada
        (WorkspaceSeasonPlayer) aunque su Player.team apunte a OTRO equipo (identidad compartida)
        debe poder guardar posición. Antes el guardrail exigía Player.team == team y devolvía 400
        (not_in_team) -> la posición no persistía y al recargar volvía al sitio."""
        other_team = Team.objects.create(name='Club Origen', slug='club-origen')
        shared = Player.objects.create(team=other_team, name='Cedido', position='Extremo', number=11, is_active=True)
        # Está en MI equipo por membresía de temporada, no por Player.team.
        WorkspaceSeasonPlayer.objects.create(
            season=self.workspace.active_season, player=shared, team=self.team,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        self.assertNotEqual(shared.team_id, self.team.id)
        resp = self._save(team_id=self.team.id, player_id=shared.id, left='60', top='25')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        layout = CoachPitchBoardLayout.objects.get(team=self.team)
        self.assertEqual(layout.positions.get(str(shared.id)), [60.0, 25.0])
