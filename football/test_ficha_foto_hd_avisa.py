"""La ficha AVISA cuando su dibujo se está rehaciendo, y se recarga sola cuando está.

El dibujo de la ficha es una FOTO del editor hecha con Playwright en segundo plano: tarda cerca de
un minuto. Se encolaba en silencio, así que la página que ya estabas mirando se quedaba con el
dibujo viejo y nada te decía que venía uno nuevo. Desde fuera parecía que editar la pizarra no
actualizaba la ficha; medido en producción el 2026-08-08, la foto SÍ se hacía (y en ~1 minuto).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import SessionTask, Team, TrainingMicrocycle, TrainingSession, Workspace

HOY = datetime.date(2026, 8, 6)
CANVAS = {"version": "5.3.0", "objects": [
    {"type": "rect", "left": 300, "top": 88, "width": 96, "height": 16, "fill": "#fff",
     "data": {"kind": "goal_mini"}},
]}


class LaFichaAvisaDeLaFotoTests(TestCase):
    def _tarea(self, *, con_foto):
        User = get_user_model()
        user = User.objects.create_superuser(f"u{int(con_foto)}", "u@x.es", "x")
        team = Team.objects.create(name=f"Eq{int(con_foto)}", slug=f"eq{int(con_foto)}",
                                   category="Senior", is_primary=True)
        ws = Workspace.objects.create(name=f"C{int(con_foto)}", kind=Workspace.KIND_CLUB,
                                      owner_user=user, primary_team=team)
        mc = TrainingMicrocycle.objects.create(
            team=team, week_start=HOY - datetime.timedelta(days=3), week_end=HOY + datetime.timedelta(days=3)
        )
        ses = TrainingSession.objects.create(microcycle=mc, session_date=HOY)
        layout = {"meta": {"graphic_editor": {"canvas_state": CANVAS},
                           "pitch_preset": "full_pitch", "pitch_orientation": "landscape"}}
        task = SessionTask.objects.create(
            session=ses, title="Con pizarra", block=SessionTask.BLOCK_MAIN_1, duration_minutes=20,
            tactical_layout=layout, task_layout_light=layout,
        )
        if con_foto:
            # Una foto YA al día: mismo nombre "board-hd" y la firma del dibujo guardada.
            from football.task_board_snapshot import META_SIG_KEY, board_signature

            task.task_preview_image.name = f"session-tasks-preview/task-{task.id}-board-hd.jpg"
            layout["meta"][META_SIG_KEY] = board_signature(task)
            task.tactical_layout = layout
            task.task_layout_light = layout
            task.save(update_fields=["task_preview_image", "tactical_layout", "task_layout_light"])
        self.client.force_login(user)
        s = self.client.session
        s["active_workspace_id"] = int(ws.id)
        s.save()
        return task

    def test_sin_foto_al_dia_la_ficha_lo_avisa(self):
        task = self._tarea(con_foto=False)
        html = self.client.get(reverse("session-task-detail", args=[task.id])).content.decode("utf-8", "replace")
        self.assertIn("data-board-hd-pendiente", html,
                      "la ficha no avisa de que el dibujo se está rehaciendo")
        self.assertIn("Actualizando el dibujo de la ficha", html)

    def test_con_la_foto_al_dia_NO_molesta(self):
        task = self._tarea(con_foto=True)
        html = self.client.get(reverse("session-task-detail", args=[task.id])).content.decode("utf-8", "replace")
        self.assertNotIn("data-board-hd-pendiente", html,
                         "avisa de una foto pendiente que ya está hecha")

    def test_el_aviso_consulta_el_estado_y_recarga(self):
        task = self._tarea(con_foto=False)
        html = self.client.get(reverse("session-task-detail", args=[task.id])).content.decode("utf-8", "replace")
        self.assertIn(reverse("session-task-board-hd", args=[task.id]), html,
                      "el aviso no sabe a qué endpoint preguntar")
        self.assertIn("location.reload()", html, "no se recarga cuando la foto está lista")
