"""En la pizarra, quien está fichado sale con la equipación.

Había dos interruptores distintos y el entrenador sólo conoce uno: la ficha federativa (que da
el club) y la confirmación de temporada (planificación interna, el "Sigue / No sigue"). Mandaba
la segunda, así que un jugador con licencia salía "A prueba" en chándal sólo porque nadie había
tocado su fila de temporada. El 2026-08-04 le pasaba a cuatro jugadores del senior.

El chándal sigue avisando de quien NO tiene licencia: eso sí es no estar fichado.
"""

from datetime import date

from django.test import TestCase

from football.models import Player, Team, Workspace, WorkspaceSeason, WorkspaceSeasonPlayer
from football.views import _build_coach_pitch_board_players


class PizarraFichadosTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='C.D. Ejemplo', slug='cd-ejemplo-pizarra', is_primary=True)
        self.workspace = Workspace.objects.create(name='Club Ejemplo', slug='club-ejemplo-pizarra')
        self.season = WorkspaceSeason.objects.create(
            workspace=self.workspace, label='2026/2027',
            start_date=date(2026, 7, 1), end_date=date(2027, 6, 30),
        )

    def _jugador(self, nombre, *, ficha):
        return Player.objects.create(team=self.team, name=nombre, has_federative_license=ficha)

    def _membresia(self, player, *, confirmada):
        return WorkspaceSeasonPlayer.objects.create(
            season=self.season,
            player=player,
            team=self.team,
            is_confirmed=confirmada,
            status=(
                WorkspaceSeasonPlayer.STATUS_CONFIRMED if confirmada else WorkspaceSeasonPlayer.STATUS_PENDING
            ),
        )

    def _fila(self, player, memberships=None):
        filas = _build_coach_pitch_board_players(self.team, [player], memberships or {}, set())
        return filas[0] if filas else {}

    def test_con_ficha_y_sin_confirmar_sale_con_equipacion(self):
        """El caso que fallaba: fichado por el club, sin tocar su fila de temporada."""
        p = self._jugador('Nizar Zouki', ficha=True)
        fila = self._fila(p, {p.id: self._membresia(p, confirmada=False)})
        self.assertEqual(fila.get('state'), 'available')
        self.assertEqual(fila.get('state_label'), 'Disponible')
        self.assertNotIn('chandal', str(fila.get('avatar') or ''))

    def test_con_ficha_y_confirmado_sale_con_equipacion(self):
        p = self._jugador('Tadeo', ficha=True)
        fila = self._fila(p, {p.id: self._membresia(p, confirmada=True)})
        self.assertEqual(fila.get('state'), 'available')

    def test_con_ficha_y_sin_fila_de_temporada_sale_con_equipacion(self):
        p = self._jugador('Antonio', ficha=True)
        fila = self._fila(p, {})
        self.assertEqual(fila.get('state'), 'available')

    def test_sin_ficha_sigue_avisando_con_chandal(self):
        """No tener licencia sí es no estar fichado: el aviso se queda."""
        p = self._jugador('Reno', ficha=False)
        fila = self._fila(p, {})
        self.assertEqual(fila.get('state'), 'trial')
        self.assertIn('chandal', str(fila.get('avatar') or ''))

    def test_el_lesionado_manda_sobre_todo(self):
        p = self._jugador('Lesionado', ficha=True)
        filas = _build_coach_pitch_board_players(self.team, [p], {}, {p.id})
        self.assertEqual(filas[0].get('state'), 'injured')
        self.assertIn('crutches', str(filas[0].get('avatar') or ''))
