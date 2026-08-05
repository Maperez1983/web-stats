from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from football.models import (
    Club,
    SessionTask,
    SessionTaskCollection,
    SessionTaskCollectionItem,
    Team,
    TrainingMicrocycle,
    TrainingSession,
)
from football.views import _ai_trainer_suggest_tasks_for_session


class TaskRecommenderTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        today = timezone.localdate()
        # Microciclo BIBLIOTECA con una tarea (así el motor la considera candidata).
        lib_mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca test", week_start=today - timedelta(days=14), week_end=today - timedelta(days=8)
        )
        lib_sess = TrainingSession.objects.create(microcycle=lib_mc, session_date=today, focus="")
        self.lib_task = SessionTask.objects.create(
            session=lib_sess, block="main_1", title="Rondo de presión tras pérdida",
            objective="Trabajar la presión tras pérdida en campo rival", duration_minutes=12,
        )

    def test_recommends_matching_library_task_from_session_context(self):
        today = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana 1", week_start=today, week_end=today + timedelta(days=6),
            objective="Presión tras pérdida",
        )
        session = TrainingSession.objects.create(
            microcycle=mc, session_date=today, focus="Presión tras pérdida en campo rival",
        )
        rec = _ai_trainer_suggest_tasks_for_session(session, limit=6)
        self.assertIn(self.lib_task.id, [getattr(t, "id", None) for t in rec])

    def test_no_context_returns_empty(self):
        today = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana 2", week_start=today + timedelta(days=7), week_end=today + timedelta(days=13)
        )
        session = TrainingSession.objects.create(microcycle=mc, session_date=today, focus="")
        self.assertEqual(_ai_trainer_suggest_tasks_for_session(session), [])


class RecomendadorPremiumTests(TestCase):
    """Lo que hace que la recomendación valga: metodología por delante del parecido de
    palabras, material del club visible desde cualquier categoría, y variedad."""

    def setUp(self):
        self.club = Club.objects.create(name="CD Prueba")
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True, club=self.club)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Biblioteca test",
            week_start=hoy - timedelta(days=14),
            week_end=hoy - timedelta(days=8),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")

    def _tarea(self, titulo, *, meta=None, objetivo="", equipo_sesion=None):
        return SessionTask.objects.create(
            session=equipo_sesion or self.biblioteca,
            block="main_1",
            title=titulo,
            objective=objetivo,
            duration_minutes=12,
            tactical_layout={"meta": meta or {}},
        )

    def _sesion(self, **campos):
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        return TrainingSession.objects.create(microcycle=mc, session_date=hoy, **campos)

    def test_la_metodologia_manda_sobre_repetir_palabras(self):
        etiquetada = self._tarea(
            "Salida desde portero",
            meta={"game_moment": "offensive_organization"},
            objetivo="Sacar limpio jugando",
        )
        cotorra = self._tarea(
            "Charla",
            objetivo="posesion posesion posesion posesion posesion posesion",
        )
        sesion = self._sesion(focus="posesion", game_moment="offensive_organization")
        rec = _ai_trainer_suggest_tasks_for_session(sesion, limit=6)
        ids = [t.id for t in rec]
        self.assertIn(etiquetada.id, ids)
        self.assertIn(cotorra.id, ids)
        self.assertLess(
            ids.index(etiquetada.id), ids.index(cotorra.id),
            "la tarea del momento de juego que se entrena tiene que ir por delante",
        )
        self.assertIn("mismo momento de juego", getattr(rec[0], "ai_trainer_reasons", []))

    def test_una_palabra_no_casa_dentro_de_otra(self):
        # "area" vivía dentro de "tarea": la búsqueda era por subcadena y colaba cualquier cosa.
        self._tarea("Tarea de rueda de pases", objetivo="Rueda de pases con dos apoyos")
        sesion = self._sesion(focus="area")
        self.assertEqual(_ai_trainer_suggest_tasks_for_session(sesion, limit=6), [])

    def test_las_tareas_del_libro_se_ven_desde_otra_categoria(self):
        del_libro = self._tarea("Rondo 4x4 del libro", objetivo="Circular la pelota en posesion")
        carpeta = SessionTaskCollection.objects.create(
            team=self.team, repository=SessionTaskCollection.REPO_INTERACTIVE, name="Tareas importadas"
        )
        SessionTaskCollectionItem.objects.create(collection=carpeta, task=del_libro)

        cadete = Team.objects.create(name="Cadete", slug="cadete", club=self.club)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=cadete, title="Semana cadete", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        sesion = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="posesion")
        ids = [t.id for t in _ai_trainer_suggest_tasks_for_session(sesion, limit=6)]
        self.assertIn(del_libro.id, ids, "el material del club tiene que llegar a todas las categorias")

    def test_no_devuelve_seis_veces_lo_mismo(self):
        for i in range(6):
            self._tarea(f"Rondo {i}", meta={"task_family": "rondo"}, objetivo="posesion en rondo")
        for i in range(3):
            self._tarea(f"Circuito {i}", meta={"task_family": "circuito"}, objetivo="posesion en circuito")
        sesion = self._sesion(focus="posesion")
        rec = _ai_trainer_suggest_tasks_for_session(sesion, limit=4)
        familias = [getattr(t, "task_family", "") for t in rec]
        self.assertLessEqual(familias.count("rondo"), 2, "no puede devolver la misma familia una y otra vez")
        self.assertEqual(len(rec), 4, "y aun asi tiene que devolver las que se le piden")
