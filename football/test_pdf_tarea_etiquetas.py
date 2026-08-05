"""En el PDF de la tarea, la metodología se lee en cristiano.

El resumen de "Organización" volcaba el valor interno tal cual: en la ficha del 4c4 en seis
subzonas salía «cognitive», en inglés (2026-08-05). Dos líneas más arriba, en "Estructura
dominante", ese mismo valor ya se traducía; al resumen se le había olvidado.
"""

from datetime import date

from django.test import TestCase

from football.models import SessionTask, Team, TrainingMicrocycle, TrainingSession


class EtiquetasDelPdfTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='C.D. Ejemplo', slug='cd-ejemplo-pdf', is_primary=True)
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title='Semana', week_start=date(2026, 8, 3), week_end=date(2026, 8, 9)
        )
        self.sesion = TrainingSession.objects.create(
            microcycle=mc, session_date=date(2026, 8, 4), duration_minutes=90
        )

    def _contexto(self, meta):
        from django.test import RequestFactory

        from football.views import _build_task_pdf_context

        tarea = SessionTask.objects.create(
            session=self.sesion, title='Tarea', tactical_layout={'meta': meta}
        )
        peticion = RequestFactory().get('/')
        return _build_task_pdf_context(
            peticion, self.team, self.sesion, self.sesion.microcycle, tarea,
            tarea.tactical_layout, pdf_style='club', allow_live_canvas_render=False,
        )

    def test_la_estructura_sale_traducida(self):
        ctx = self._contexto({'dominant_structure': 'cognitive'})
        resumen = str(ctx.get('structure_summary_label') or '')
        self.assertNotIn('cognitive', resumen.lower())
        self.assertIn('ognitiv', resumen)  # Cognitiva

    def test_un_valor_desconocido_no_rompe(self):
        ctx = self._contexto({'dominant_structure': 'lo_que_sea'})
        self.assertIn('lo_que_sea', str(ctx.get('structure_summary_label') or ''))

    def test_sin_estructura_no_deja_guiones_sueltos(self):
        ctx = self._contexto({'organization': 'Grupos de 4'})
        self.assertEqual(str(ctx.get('structure_summary_label') or '').strip(), 'Grupos de 4')
