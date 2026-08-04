"""El recomendador aprende de lo que el entrenador pone en el campo.

Hasta ahora los pesos sólo se movían desde dos botones de la pantalla IA-Trainer. Resultado
medido el 2026-08-04 en producción: 288 tareas indexadas, 1.302 conceptos en el diccionario
y **cero** filas en AiTrainerTokenWeight. El sistema llevaba una temporada entera sin aprender
nada porque la señal estaba enchufada a una pantalla que no se usa.

La señal buena es la sesión: lo que el entrenador decide entrenar. Guardar una plantilla en la
biblioteca no lo es.
"""

from datetime import date

from django.test import TestCase

from football.ai_trainer import aprender_de_tarea_usada
from football.library_repositories import LIBRARY_MICROCYCLE_MARKER
from football.models import AiTrainerTokenWeight, SessionTask, Team, TrainingMicrocycle, TrainingSession


class AprenderDelUsoTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='C.D. Ejemplo', slug='cd-ejemplo-ia', is_primary=True)
        self.microciclo = TrainingMicrocycle.objects.create(
            team=self.team, title='Semana 1', week_start=date(2026, 8, 3), week_end=date(2026, 8, 9)
        )
        self.sesion = TrainingSession.objects.create(
            microcycle=self.microciclo, session_date=date(2026, 8, 4), focus='Salida', duration_minutes=90
        )
        self.biblioteca = TrainingMicrocycle.objects.create(
            team=self.team, title='Biblioteca de tareas', notes=LIBRARY_MICROCYCLE_MARKER,
            week_start=date(2000, 1, 3), week_end=date(2000, 1, 9)
        )
        self.sesion_biblioteca = TrainingSession.objects.create(
            microcycle=self.biblioteca, session_date=date(2000, 1, 4), duration_minutes=60
        )

    def _crear_tarea(self, sesion, **extra):
        datos = {
            'title': 'Rondo de salida',
            'objective': 'Trabajar la salida de balón desde portero',
            'coaching_points': 'Perfil abierto, apoyos escalonados',
        }
        datos.update(extra)
        return SessionTask.objects.create(session=sesion, **datos)

    def test_una_tarea_en_sesion_real_deja_conceptos_aprendidos(self):
        self.assertEqual(AiTrainerTokenWeight.objects.count(), 0)
        self._crear_tarea(self.sesion)
        pesos = AiTrainerTokenWeight.objects.filter(team=self.team)
        self.assertGreater(pesos.count(), 0)
        conceptos = set(pesos.values_list('token', flat=True))
        self.assertIn('salida', conceptos)
        self.assertIn('balon', conceptos)

    def test_la_biblioteca_no_ensena_nada(self):
        """Guardar una plantilla no es decidir entrenarla."""
        self._crear_tarea(self.sesion_biblioteca)
        self.assertEqual(AiTrainerTokenWeight.objects.count(), 0)

    def test_repetir_el_concepto_lo_refuerza(self):
        self._crear_tarea(self.sesion)
        primero = AiTrainerTokenWeight.objects.get(team=self.team, token='salida').weight
        self._crear_tarea(self.sesion, title='Otra de salida')
        segundo = AiTrainerTokenWeight.objects.get(team=self.team, token='salida').weight
        self.assertGreater(segundo, primero)

    def test_editar_una_tarea_no_vuelve_a_sumar(self):
        """Retocar diez veces la misma tarea no significa que guste diez veces más."""
        tarea = self._crear_tarea(self.sesion)
        antes = AiTrainerTokenWeight.objects.get(team=self.team, token='salida').weight
        tarea.coaching_points = 'Perfil abierto, apoyos escalonados, ritmo alto'
        tarea.save()
        tarea.save()
        despues = AiTrainerTokenWeight.objects.get(team=self.team, token='salida').weight
        self.assertEqual(antes, despues)

    def test_el_peso_no_se_dispara(self):
        for _ in range(90):
            self._crear_tarea(self.sesion)
        peso = AiTrainerTokenWeight.objects.get(team=self.team, token='salida').weight
        self.assertLessEqual(peso, 25.0)

    def test_no_aprende_de_una_tarea_suelta(self):
        self.assertEqual(aprender_de_tarea_usada(None), 0)

    def test_una_tarea_sin_texto_se_guarda_igual(self):
        """La señal nunca puede impedir que se guarde el trabajo del entrenador: si no hay nada
        que aprender, no se aprende y punto."""
        tarea = SessionTask.objects.create(session=self.sesion, title='', objective='')
        self.assertIsNotNone(tarea.pk)
        self.assertEqual(AiTrainerTokenWeight.objects.count(), 0)
