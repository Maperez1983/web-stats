"""La cola de fotos HD: el encargo sobrevive a que se muera quien iba a cumplirlo.

Lo que arreglan estas pruebas pasó de verdad (2026-08-08): la tarea 1160 se quedó sin foto y sin
una sola pista de por qué. La foto se hacía en un hilo dentro del proceso web y la contabilidad
vivía en `cache`, que en producción es LocMemCache con DOS workers de gunicorn. Resultado:

  - si Render reiniciaba el worker, el hilo moría y no quedaba ni foto ni error;
  - el estado que veías dependía del worker que te contestara;
  - y tras un fallo se callaba 30 minutos sin decírselo a nadie.

Cada prueba de aquí se ha comprobado quitando el arreglo a mano: si el encargo vuelve a vivir en
memoria, fallan.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football import task_board_snapshot as fotos
from football.models import (
    SessionTask,
    TaskBoardShot,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
)

HOY = datetime.date(2026, 8, 6)
CANVAS = {"version": "5.3.0", "objects": [
    {"type": "rect", "left": 300, "top": 88, "width": 96, "height": 16, "fill": "#fff",
     "data": {"kind": "goal_mini"}},
]}


class ColaBase(TestCase):
    def _tarea(self, sufijo="a"):
        User = get_user_model()
        self.user = User.objects.create_superuser(f"u{sufijo}", f"u{sufijo}@x.es", "x")
        team = Team.objects.create(name=f"Eq{sufijo}", slug=f"eq{sufijo}",
                                   category="Senior", is_primary=True)
        self.ws = Workspace.objects.create(name=f"C{sufijo}", kind=Workspace.KIND_CLUB,
                                           owner_user=self.user, primary_team=team)
        mc = TrainingMicrocycle.objects.create(
            team=team, week_start=HOY - datetime.timedelta(days=3),
            week_end=HOY + datetime.timedelta(days=3),
        )
        ses = TrainingSession.objects.create(microcycle=mc, session_date=HOY)
        layout = {"meta": {"graphic_editor": {"canvas_state": CANVAS},
                           "pitch_preset": "full_pitch", "pitch_orientation": "landscape"}}
        return SessionTask.objects.create(
            session=ses, title="Con pizarra", block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=20, tactical_layout=layout, task_layout_light=layout,
        )

    def _entrar(self):
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = int(self.ws.id)
        s.save()


class ElEncargoQuedaEscritoTests(ColaBase):
    def test_abrir_la_ficha_deja_el_encargo_en_la_BASE(self):
        """Lo que antes era un hilo en RAM ahora es una fila. Es TODO el arreglo."""
        task = self._tarea()
        self._entrar()
        self.client.get(reverse("session-task-detail", args=[task.id]))

        shot = TaskBoardShot.objects.get(task_id=task.id)
        self.assertEqual(shot.state, TaskBoardShot.PENDIENTE)
        self.assertEqual(shot.signature, fotos.board_signature(task))
        self.assertEqual(shot.requested_by_id, self.user.id,
                         "sin saber quién la pidió no hay sesión con la que abrir el editor")

    def test_visitar_mil_veces_no_acumula_trabajo(self):
        task = self._tarea()
        self._entrar()
        for _ in range(4):
            self.client.get(reverse("session-task-detail", args=[task.id]))
        self.assertEqual(TaskBoardShot.objects.filter(task_id=task.id).count(), 1)

    def test_si_cambia_el_dibujo_los_intentos_vuelven_a_cero(self):
        """Una pizarra nueva merece sus reintentos aunque la anterior se rindiera."""
        task = self._tarea()
        fotos.request_snapshot(task, self.user)
        shot = TaskBoardShot.objects.get(task_id=task.id)
        shot.attempts = TaskBoardShot.MAX_INTENTOS
        shot.state = TaskBoardShot.RENDIDA
        shot.last_error = "lo que fuera"
        shot.save()

        layout = dict(task.tactical_layout)
        layout["meta"] = dict(layout["meta"])
        layout["meta"]["pitch_preset"] = "half_pitch"      # otro dibujo -> otra firma
        task.tactical_layout = layout
        task.save(update_fields=["tactical_layout"])
        fotos.request_snapshot(task, self.user)

        shot.refresh_from_db()
        self.assertEqual(shot.attempts, 0)
        self.assertEqual(shot.state, TaskBoardShot.PENDIENTE)
        self.assertEqual(shot.last_error, "")


class ElAlquilerDevuelveElEncargoTests(ColaBase):
    def test_dos_procesos_no_cogen_el_mismo_encargo(self):
        task = self._tarea()
        fotos.request_snapshot(task, self.user)

        primero = fotos.claim_pending(limit=5)
        segundo = fotos.claim_pending(limit=5)
        self.assertEqual(len(primero), 1)
        self.assertEqual(segundo, [], "un encargo alquilado no puede cogerlo otro a la vez")

    def test_si_el_proceso_se_muere_el_encargo_VUELVE_a_la_cola(self):
        """El agujero exacto de la tarea 1160: el hilo moría y el encargo se perdía entero."""
        task = self._tarea()
        fotos.request_snapshot(task, self.user)
        cogido = fotos.claim_pending(limit=1)[0]

        # Se muere sin decir nada: nadie llama a mark_done ni a mark_failed. Lo único que pasa
        # es que el alquiler caduca.
        cogido.leased_until = timezone.now() - datetime.timedelta(seconds=1)
        cogido.save(update_fields=["leased_until"])

        self.assertEqual(len(fotos.claim_pending(limit=1)), 1,
                         "un encargo huérfano se queda colgado para siempre")


class RendirseSeDiceTests(ColaBase):
    def test_cada_fallo_espera_mas_pero_no_media_hora_a_ciegas(self):
        task = self._tarea()
        fotos.request_snapshot(task, self.user)
        shot = TaskBoardShot.objects.get(task_id=task.id)

        fotos.mark_failed(shot, "Chromium no arrancó")
        self.assertEqual(shot.attempts, 1)
        self.assertEqual(shot.state, TaskBoardShot.PENDIENTE)
        self.assertLess(shot.next_try_at, timezone.now() + datetime.timedelta(minutes=2),
                        "el primer reintento no puede tardar media hora")
        self.assertIn("Chromium", shot.last_error)

    def test_tras_varios_intentos_se_rinde_PERO_deja_el_motivo(self):
        task = self._tarea()
        fotos.request_snapshot(task, self.user)
        shot = TaskBoardShot.objects.get(task_id=task.id)
        for _ in range(TaskBoardShot.MAX_INTENTOS):
            fotos.mark_failed(shot, "la pizarra no llegó a estar lista")

        shot.refresh_from_db()
        self.assertEqual(shot.state, TaskBoardShot.RENDIDA)
        self.assertEqual(shot.last_error, "la pizarra no llegó a estar lista",
                         "rendirse en silencio es lo que nos costó una tarde")
        self.assertEqual(fotos.claim_pending(limit=5), [],
                         "un encargo rendido no puede seguir consumiendo turnos")

    def test_la_ficha_ENSENA_el_motivo_y_deja_reintentar(self):
        task = self._tarea()
        self._entrar()
        fotos.request_snapshot(task, self.user)
        shot = TaskBoardShot.objects.get(task_id=task.id)
        for _ in range(TaskBoardShot.MAX_INTENTOS):
            fotos.mark_failed(shot, "la pizarra no llegó a estar lista")

        html = self.client.get(reverse("session-task-detail", args=[task.id])).content.decode("utf-8", "replace")
        self.assertIn("No se pudo actualizar el dibujo de la ficha", html)
        self.assertIn("la pizarra no llegó a estar lista", html,
                      "el motivo tiene que verse en la ficha, no en la memoria de un worker")
        self.assertIn("data-board-hd-reintentar", html, "sin botón, el usuario no puede hacer nada")

    def test_reintentar_a_mano_rearma_el_encargo(self):
        task = self._tarea()
        self._entrar()
        fotos.request_snapshot(task, self.user)
        shot = TaskBoardShot.objects.get(task_id=task.id)
        for _ in range(TaskBoardShot.MAX_INTENTOS):
            fotos.mark_failed(shot, "lo que fuera")

        self.client.get(reverse("session-task-board-hd", args=[task.id]) + "?force=1")

        shot.refresh_from_db()
        self.assertEqual(shot.state, TaskBoardShot.PENDIENTE)
        self.assertEqual(shot.attempts, 0)


class LaCapturaVaTambienALaPortadaTests(ColaBase):
    """La peticion era "a la portada Y a la ficha". La portada no se actualizaba NUNCA.

    En todo views.py `cover_data_b64` solo se lee. Y como la tarjeta de biblioteca pinta la
    portada ANTES que la foto de la pizarra, en las 512 tareas de produccion que tienen portada
    propia el dibujo nuevo no se veia jamas: se arreglaba la mitad invisible del problema.
    """

    def _una_foto(self):
        """Un JPEG de verdad, que es lo que `_store` recibe."""
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (2520, 2002), (40, 120, 60)).save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    def test_guardar_la_foto_REESCRIBE_la_portada(self):
        task = self._tarea()
        task.cover_data_b64 = "data:image/jpeg;base64,LA_VIEJA"
        task.save(update_fields=["cover_data_b64"])

        fotos._store(int(task.id), self._una_foto(), fotos.board_signature(task))

        task.refresh_from_db()
        self.assertTrue(task.cover_data_b64.startswith("data:image/jpeg;base64,"))
        self.assertNotIn("LA_VIEJA", task.cover_data_b64,
                         "la portada sigue siendo la vieja: la tarjeta enseñará el dibujo antiguo")

    def test_la_portada_no_engorda_la_tarjeta(self):
        """El listado ya arrastro un problema de peso por meter imagenes grandes."""
        import base64
        import io

        from PIL import Image

        task = self._tarea()
        fotos._store(int(task.id), self._una_foto(), fotos.board_signature(task))
        task.refresh_from_db()

        crudo = base64.b64decode(task.cover_data_b64.split(",", 1)[1])
        self.assertLessEqual(Image.open(io.BytesIO(crudo)).width, fotos.COVER_MAX_WIDTH)

    def test_si_la_foto_se_descarta_la_portada_NO_se_toca(self):
        """Mismo blindaje que la imagen: una foto que no vale no puede empeorar lo que hay."""
        task = self._tarea()
        task.cover_data_b64 = "data:image/jpeg;base64,LA_BUENA"
        task.save(update_fields=["cover_data_b64"])

        fotos._store(int(task.id), self._una_foto(), "firma-de-otro-dibujo")

        task.refresh_from_db()
        self.assertIn("LA_BUENA", task.cover_data_b64,
                      "se ha pisado la portada con una foto que el propio sistema descarta")


class LaFotoNoSeHaceEnElWebTests(ColaBase):
    def test_abrir_la_ficha_no_levanta_ningun_navegador(self):
        """El motivo por el que el servidor se reiniciaba: Chromium dentro del proceso web.

        Se vigila `_render`, que es la única puerta a Playwright. La espera de después NO es
        adorno: si alguien vuelve a fotografiar desde aquí lo hará en un hilo, y sin darle un
        respiro esta prueba pasaría en verde con el fallo puesto. Comprobado a mano reponiendo el
        hilo viejo (2026-08-08): con la espera, falla.
        """
        import threading
        import time

        task = self._tarea()
        self._entrar()
        llamadas = []
        original = fotos._render
        fotos._render = lambda *a, **k: llamadas.append(a) or None
        try:
            self.client.get(reverse("session-task-detail", args=[task.id]))
            time.sleep(0.3)
            for hilo in threading.enumerate():
                if str(hilo.name or "").startswith("board-snapshot"):
                    hilo.join(timeout=2)
        finally:
            fotos._render = original
        self.assertEqual(llamadas, [], "la ficha sigue fotografiando dentro del servidor web")
        self.assertFalse(
            [h.name for h in threading.enumerate() if str(h.name or "").startswith("board-snapshot")],
            "la ficha sigue lanzando hilos de foto: eso es lo que se perdía al reiniciarse el worker",
        )
