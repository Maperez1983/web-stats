"""El recomendador tiene que LLEGAR a la pantalla.

El motor estaba terminado y no lo llamaba nadie: la única función contextual sólo la
invocaban las pruebas. Esto fija la puerta, no el algoritmo.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from football.models import SessionTask, Team, TrainingMicrocycle, TrainingSession


class RecomendadorEnLaPantallaTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-pant", is_primary=True)
        hoy = timezone.localdate()
        mcb = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca pant",
            week_start=hoy - timedelta(days=21), week_end=hoy - timedelta(days=15),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mcb, session_date=hoy, focus="")
        self.principal = SessionTask.objects.create(
            session=self.biblioteca, block="main_1", title="Posesion 6x6 con apoyos",
            objective="posesion en superioridad", duration_minutes=15,
        )
        self.calma = SessionTask.objects.create(
            session=self.biblioteca, block="recovery", title="Estiramientos con posesion suave",
            objective="posesion muy suave para bajar pulsaciones", duration_minutes=8,
        )
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana pant", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        self.sesion = TrainingSession.objects.create(
            microcycle=mc, session_date=hoy, focus="posesion", md_day="md_minus_3"
        )
        User = get_user_model()
        self.user = User.objects.create_superuser("jefe", "jefe@x.com", "x")
        self.client.force_login(self.user)

    def _pantalla(self, **params):
        params.setdefault("tab", "library")
        params.setdefault("session_id", self.sesion.id)
        params.setdefault("team_id", self.team.id)
        return self.client.get("/coach/sesiones/", params)

    def test_la_biblioteca_recomienda_para_la_sesion(self):
        r = self._pantalla()
        self.assertEqual(r.status_code, 200)
        recomendadas = r.context.get("library_recommended") or []
        self.assertTrue(recomendadas, "la pantalla tiene que traer recomendaciones, no una lista vacía")
        self.assertIn(self.principal.id, [t.id for t in recomendadas])

    def test_cada_recomendacion_dice_por_que(self):
        recomendadas = self._pantalla().context.get("library_recommended") or []
        self.assertTrue(all(getattr(t, "ai_trainer_why", "") for t in recomendadas))

    def test_cada_hueco_pone_primera_la_suya(self):
        # Lo que importa no es que la lista "cambie", sino que cada hueco ponga delante la
        # tarea de ese hueco: es la diferencia entre recomendar y listar.
        con_calma = [t.id for t in (self._pantalla(block="recovery").context.get("library_recommended") or [])]
        con_principal = [t.id for t in (self._pantalla(block="main_1").context.get("library_recommended") or [])]
        self.assertEqual(con_calma[0], self.calma.id, "para la vuelta a la calma, la suya primero")
        self.assertEqual(con_principal[0], self.principal.id, "para la parte principal, la suya primero")
        self.assertNotEqual(con_calma[0], con_principal[0])

    def test_queda_registrado_lo_que_se_propuso(self):
        from football.models import AiTrainerRecomendacion

        self._pantalla()
        self.assertTrue(AiTrainerRecomendacion.objects.filter(session=self.sesion).exists())
