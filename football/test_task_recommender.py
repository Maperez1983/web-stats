from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from football.models import SessionTask, Team, TrainingMicrocycle, TrainingSession
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
