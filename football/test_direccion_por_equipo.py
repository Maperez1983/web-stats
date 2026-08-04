"""Cada equipo ve SU dirección deportiva, no la del senior.

El objetivo de ojeo colgaba sólo del club. Había un intento de filtro por `player__team` —el
equipo del jugador LOCAL vinculado—, pero un ojeado es casi siempre alguien de fuera y no tiene
ficha local: caía en la rama "sin jugador" y se veía desde todas las categorías. De ahí que el
cadete viera la dirección del senior (2026-08-04).
"""

from django.test import TestCase

from football.models import Player, ScoutingTarget, Team, Workspace
from football.scouting_scope import equipo_para_nuevo_objetivo, objetivos_del_equipo


class DireccionPorEquipoTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name='Club', slug='club-direccion')
        self.senior = Team.objects.create(name='Senior', slug='senior-dir', is_primary=True)
        self.cadete = Team.objects.create(name='Cadete', slug='cadete-dir')

    def _objetivo(self, nombre, *, team=None, player=None):
        return ScoutingTarget.objects.create(
            workspace=self.workspace, subject_name=nombre, team=team, player=player
        )

    def _ve(self, team):
        # El modelo capitaliza el nombre al guardar, así que se compara en minúsculas.
        qs = objetivos_del_equipo(ScoutingTarget.objects.filter(workspace=self.workspace), team)
        return sorted(str(n).lower() for n in qs.values_list('subject_name', flat=True))

    def test_cada_equipo_ve_lo_suyo(self):
        self._objetivo('Del senior', team=self.senior)
        self._objetivo('Del cadete', team=self.cadete)
        self.assertEqual(self._ve(self.senior), ['del senior'])
        self.assertEqual(self._ve(self.cadete), ['del cadete'])

    def test_el_ojeado_de_fuera_ya_no_se_cuela_en_todas(self):
        """El caso real: sin jugador local vinculado y asignado al senior."""
        self._objetivo('Chaval de otro club', team=self.senior)
        self.assertEqual(self._ve(self.cadete), [])
        self.assertEqual(self._ve(self.senior), ['chaval de otro club'])

    def test_sin_categoria_decidida_se_ve_desde_todas(self):
        """Un ojeado del club todavía sin categoría tiene que verse en algún sitio."""
        self._objetivo('Sin decidir')
        self.assertIn('sin decidir', self._ve(self.senior))
        self.assertIn('sin decidir', self._ve(self.cadete))

    def test_sin_equipo_propio_manda_el_equipo_del_jugador(self):
        jugador = Player.objects.create(team=self.cadete, name='Chaval a prueba')
        self._objetivo('Con ficha local', player=jugador)
        self.assertEqual(self._ve(self.cadete), ['con ficha local'])
        self.assertEqual(self._ve(self.senior), [])

    def test_el_equipo_propio_manda_sobre_el_del_jugador(self):
        jugador = Player.objects.create(team=self.cadete, name='Sube al senior')
        self._objetivo('Promociona', team=self.senior, player=jugador)
        self.assertEqual(self._ve(self.senior), ['promociona'])
        self.assertEqual(self._ve(self.cadete), [])

    def test_sin_equipo_activo_no_se_filtra(self):
        self._objetivo('Del senior', team=self.senior)
        self._objetivo('Del cadete', team=self.cadete)
        self.assertEqual(len(self._ve(None)), 2)

    def test_el_objetivo_nuevo_nace_en_su_categoria(self):
        self.assertEqual(equipo_para_nuevo_objetivo(self.cadete), self.cadete)
        self.assertIsNone(equipo_para_nuevo_objetivo(None))
