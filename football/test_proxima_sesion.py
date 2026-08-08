"""La "Próxima sesión" de la home de Entrenamiento tiene que ser un ENTRENAMIENTO.

La biblioteca de tareas se guarda como sesión (con su microciclo centinela del año 2000)
y ganaba la carrera por fecha: la tarjeta anunciaba "Próxima sesión: Biblioteca
Interactiva · Entrenador" en lugar del entrenamiento siguiente.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    Competition,
    Group,
    Match,
    Season,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceTeam,
)


class ProximaSesionTests(TestCase):
    def setUp(self):
        comp = Competition.objects.create(name="Liga PS", slug="liga-ps", region="Andalucia")
        temporada = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        grupo = Group.objects.create(season=temporada, name="G", slug="g-ps")
        self.team = Team.objects.create(name="Benagalbón PS", slug="ben-ps", group=grupo, is_primary=True)
        self.rival = Team.objects.create(name="Mijas PS", slug="mijas-ps", group=grupo)
        self.temporada = temporada
        ws = Workspace.objects.create(
            name="Benagalbón PS", slug="ben-ps-ws", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceTeam.objects.create(workspace=ws, team=self.team, is_default=True)
        user = get_user_model().objects.create_user("mister_ps", password="x", is_superuser=True, is_staff=True)
        self.client.force_login(user)
        self.hoy = date.today()

    def _sesion(self, cuando, foco, *, semana=None, **extra):
        inicio = semana or (cuando - timedelta(days=cuando.weekday()))
        ciclo, _ = TrainingMicrocycle.objects.get_or_create(
            team=self.team, week_start=inicio, defaults={"week_end": inicio + timedelta(days=6)}
        )
        return TrainingSession.objects.create(microcycle=ciclo, session_date=cuando, focus=foco, **extra)

    def _partido(self, cuando):
        return Match.objects.create(
            season=self.temporada,
            home_team=self.rival,
            away_team=self.team,
            date=cuando,
            context=Match.CONTEXT_FRIENDLY,
        )

    def _panel(self):
        respuesta = self.client.get(reverse("sessions"), {"team": self.team.id})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.context

    def _proxima(self):
        return self._panel()["home_next_session"]

    def test_la_biblioteca_no_es_la_proxima_sesion(self):
        # La biblioteca cae ANTES y por fecha ganaba.
        self._sesion(self.hoy, "Biblioteca Interactiva · Entrenador", semana=date(2000, 1, 3))
        entreno = self._sesion(self.hoy + timedelta(days=3), "Entrenamiento")

        proxima = self._proxima()
        self.assertIsNotNone(proxima)
        self.assertEqual(proxima["id"], entreno.id)
        self.assertEqual(proxima["focus"], "Entrenamiento")

    def test_tampoco_lo_es_una_sesion_marcada_para_borrar(self):
        self._sesion(self.hoy, "Entrenamiento · 🗑️ #138")
        entreno = self._sesion(self.hoy + timedelta(days=2), "Entrenamiento")
        self.assertEqual(self._proxima()["id"], entreno.id)

    def test_una_sesion_cancelada_sigue_sin_contar(self):
        self._sesion(self.hoy, "Entrenamiento", status=TrainingSession.STATUS_CANCELED)
        entreno = self._sesion(self.hoy + timedelta(days=1), "Entrenamiento")
        self.assertEqual(self._proxima()["id"], entreno.id)

    def test_si_no_queda_ningun_entrenamiento_no_se_inventa_uno(self):
        self._sesion(self.hoy, "Biblioteca Interactiva · Entrenador", semana=date(2000, 1, 3))
        self.assertIsNone(self._proxima())

    def test_el_entrenamiento_de_hoy_sigue_siendo_el_proximo(self):
        hoy = self._sesion(self.hoy, "Entrenamiento")
        self._sesion(self.hoy + timedelta(days=2), "Entrenamiento")
        self.assertEqual(self._proxima()["id"], hoy.id)

    def test_si_lo_siguiente_es_un_partido_el_panel_habla_del_partido(self):
        """El sábado 8 tocaba partido contra el Mijas, no una sesión."""
        partido = self._partido(self.hoy + timedelta(days=1))
        self._sesion(self.hoy + timedelta(days=4), "Entrenamiento")

        ctx = self._panel()
        self.assertIsNotNone(ctx["home_next_match"])
        self.assertEqual(ctx["home_next_match"]["id"], partido.id)
        self.assertEqual(ctx["home_next_match"]["rival"], self.rival.display_name)
        self.assertFalse(ctx["home_next_match"]["en_casa"], "jugamos fuera")

    def test_si_el_entrenamiento_llega_antes_manda_el_entrenamiento(self):
        entreno = self._sesion(self.hoy + timedelta(days=1), "Entrenamiento")
        self._partido(self.hoy + timedelta(days=5))

        ctx = self._panel()
        self.assertIsNone(ctx["home_next_match"])
        self.assertEqual(ctx["home_next_session"]["id"], entreno.id)

    def test_un_partido_ya_jugado_no_es_lo_siguiente(self):
        self._partido(self.hoy - timedelta(days=3))
        entreno = self._sesion(self.hoy + timedelta(days=2), "Entrenamiento")

        ctx = self._panel()
        self.assertIsNone(ctx["home_next_match"])
        self.assertEqual(ctx["home_next_session"]["id"], entreno.id)
