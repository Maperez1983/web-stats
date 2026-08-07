"""Dirección: las figuras salen de hechos (haber venido), no de etiquetas.

Objetivo = si quiere, lo firmamos. Ojeo = hay que verlo. Prueba = está con nosotros.
"""
from datetime import date, timedelta

from django.test import TestCase

from football.models import (
    Competition,
    ConvocationRecord,
    Group,
    Match,
    Player,
    ScoutingTarget,
    Season,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
)
from football.views import _direccion_figuras


class FigurasDeDireccionTests(TestCase):
    def setUp(self):
        comp = Competition.objects.create(name="Liga Dir", slug="liga-dir", region="Andalucia")
        temporada = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        grupo = Group.objects.create(season=temporada, name="Grupo D", slug="grupo-d")
        self.team = Team.objects.create(name="Benagalbón D", slug="benagalbon-d", group=grupo, is_primary=True)
        self.rival = Team.objects.create(name="Rival D", slug="rival-d", group=grupo)
        self.temporada = temporada
        self.workspace = Workspace.objects.create(
            name="Benagalbón D", slug="ben-d-ws", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        self.hoy = date.today()

    def _ficha(self, nombre, *, status=ScoutingTarget.STATUS_WATCHLIST, con_jugador=False):
        jugador = Player.objects.create(team=self.team, name=nombre) if con_jugador else None
        return ScoutingTarget.objects.create(
            workspace=self.workspace, team=self.team, subject_name=nombre, status=status, player=jugador
        )

    def _sesion_cerrada(self, cuando):
        ciclo, _ = TrainingMicrocycle.objects.get_or_create(
            team=self.team,
            week_start=cuando - timedelta(days=cuando.weekday()),
            defaults={"week_end": cuando + timedelta(days=6 - cuando.weekday())},
        )
        return TrainingSession.objects.create(
            microcycle=ciclo, session_date=cuando, focus="Entreno", status=TrainingSession.STATUS_DONE
        )

    def _partido(self, cuando, *, cerrado=True):
        return Match.objects.create(
            season=self.temporada, home_team=self.team, away_team=self.rival, date=cuando, is_closed=cerrado
        )

    def _grupo_de(self, ficha):
        grupos = _direccion_figuras(self.team, list(ScoutingTarget.objects.all()))
        for clave, fichas in grupos.items():
            if any(f.id == ficha.id for f in fichas):
                return clave
        return None

    def test_quien_entrena_en_una_sesion_cerrada_esta_probando(self):
        t = self._ficha("Nizar", con_jugador=True)
        sesion = self._sesion_cerrada(self.hoy - timedelta(days=2))
        TrainingSessionAttendance.objects.create(session=sesion, player=t.player, status="present")
        self.assertEqual(self._grupo_de(t), "prueba_dentro")

    def test_la_prueba_tambien_vale_en_partido(self):
        """Salva no entrena y sólo juega amistosos: tiene que salir como que está probando."""
        t = self._ficha("Salva", con_jugador=True)
        partido = self._partido(self.hoy - timedelta(days=2))
        conv = ConvocationRecord.objects.create(team=self.team, match=partido)
        conv.players.add(t.player)
        self.assertEqual(self._grupo_de(t), "prueba_dentro")

    def test_quien_vino_hace_un_mes_pasa_a_decidir(self):
        t = self._ficha("Antiguo", con_jugador=True)
        sesion = self._sesion_cerrada(self.hoy - timedelta(days=40))
        TrainingSessionAttendance.objects.create(session=sesion, player=t.player, status="present")
        self.assertEqual(self._grupo_de(t), "prueba_probado")

    def test_convocado_a_un_partido_que_no_se_ha_jugado_esta_citado(self):
        t = self._ficha("Ariel", con_jugador=True)
        partido = self._partido(self.hoy + timedelta(days=3), cerrado=False)
        conv = ConvocationRecord.objects.create(team=self.team, match=partido)
        conv.players.add(t.player)
        self.assertEqual(self._grupo_de(t), "prueba_citado")

    def test_una_sesion_sin_cerrar_no_cuenta_como_prueba(self):
        """Los entrenos sólo cuentan cuando se cierra la sesión: si no, el dato es provisional."""
        t = self._ficha("Sin cerrar", con_jugador=True)
        ciclo, _ = TrainingMicrocycle.objects.get_or_create(
            team=self.team, week_start=self.hoy, defaults={"week_end": self.hoy + timedelta(days=6)}
        )
        abierta = TrainingSession.objects.create(microcycle=ciclo, session_date=self.hoy, focus="Entreno")
        TrainingSessionAttendance.objects.create(session=abierta, player=t.player, status="present")
        self.assertEqual(self._grupo_de(t), "ojeo")

    def test_objetivo_y_ojeo_se_distinguen(self):
        objetivo = self._ficha("Samsong", status=ScoutingTarget.STATUS_TARGET)
        ojeo = self._ficha("Gordillo", status=ScoutingTarget.STATUS_WATCHLIST)
        self.assertEqual(self._grupo_de(objetivo), "objetivo")
        self.assertEqual(self._grupo_de(ojeo), "ojeo")

    def test_el_fichado_va_a_plantilla_y_el_descartado_no_aparece(self):
        fichado = self._ficha("Harley", status=ScoutingTarget.STATUS_SIGNED, con_jugador=True)
        fuera = self._ficha("Descartado", status=ScoutingTarget.STATUS_DISCARDED)
        self.assertEqual(self._grupo_de(fichado), "plantilla")
        self.assertIsNone(self._grupo_de(fuera))
