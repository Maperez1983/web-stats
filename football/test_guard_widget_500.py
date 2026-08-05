"""El panel del guardián no puede tumbar la página que lo lleva.

Una fila sin la clave `summary` lanzaba VariableDoesNotExist (una clave ausente COMO
ARGUMENTO de filtro no se perdona) y devolvía un 500 en todas las pantallas con el widget.
"""

from django.template import Context, Template
from django.test import TestCase


class PanelDelGuardianTests(TestCase):
    PLANTILLA = '{% firstof row.priority_reason row.result_summary row.summary "Sin detalle" %}'

    def _pinta(self, fila):
        return Template(self.PLANTILLA).render(Context({"row": fila}))

    def test_fila_sin_summary(self):
        fila = {
            "kind": "task",
            "title": "Blockers activos: 1",
            "status": "completed",
            "result_summary": "3/3 herramientas completadas correctamente.",
        }
        self.assertEqual(self._pinta(fila), "3/3 herramientas completadas correctamente.")

    def test_fila_vacia(self):
        self.assertEqual(self._pinta({}), "Sin detalle")

    def test_prioriza_el_motivo(self):
        self.assertEqual(
            self._pinta({"priority_reason": "incidencia crítica", "result_summary": "x"}),
            "incidencia crítica",
        )
