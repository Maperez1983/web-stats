"""La ficha enseña el dibujo ORIGINAL hasta que alguien revisa la pizarra a mano.

Una recreación automática con un fallo tonto es peor que no tenerla: el entrenador se fía de
lo que ve. Así que manda el dibujo del libro hasta que un humano abra la tarea y la guarde.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from football.models import SessionTask, Team, TrainingMicrocycle, TrainingSession


class FichaEnsenaElOriginalTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-rev", is_primary=True)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca rev",
            week_start=hoy - timedelta(days=14), week_end=hoy - timedelta(days=8),
        )
        self.sesion = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")

    def _tarea(self, meta):
        return SessionTask.objects.create(
            session=self.sesion, block="main_1", title="Del libro", duration_minutes=12,
            tactical_layout={"meta": meta},
        )

    def test_sin_revisar_no_lleva_la_marca(self):
        t = self._tarea({})
        self.assertFalse((t.tactical_layout.get("meta") or {}).get("revisada_a_mano"))

    def test_la_marca_se_respeta_al_guardarla(self):
        t = self._tarea({"revisada_a_mano": True})
        t.refresh_from_db()
        self.assertTrue((t.tactical_layout.get("meta") or {}).get("revisada_a_mano"))

    def test_la_marca_no_se_pierde_en_la_copia_ligera(self):
        # La copia ligera es la que leen los listados y la ficha: si la marca no viaja ahí,
        # la pantalla no puede saber si la tarea está revisada.
        t = self._tarea({"revisada_a_mano": True})
        t.refresh_from_db()
        ligero = t.task_layout_light or {}
        self.assertTrue((ligero.get("meta") or {}).get("revisada_a_mano"))
