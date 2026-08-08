"""Que ninguna consulta del asistente se rompa contra la base de datos.

Esto existe por un fallo concreto y repetible: `responder_entrenos_semana` filtraba por
`team=` cuando la sesión cuelga del `microcycle`, y encadenaba `.order_by()` a
`_sesiones_de_verdad`, que devuelve una LISTA. Las dos cosas revientan en cuanto se tocan los
datos de verdad —y ninguna se ve leyendo el código, porque el `try/except` de `responder()` se
las traga y la pregunta cae al guardián, que tarda nueve segundos en decir una cosa que no
tiene nada que ver. Desde fuera parece que el asistente "no entiende la frase".

Por eso el test no comprueba el texto de la respuesta: **ejecuta cada responder** contra una
base de datos vacía. Sin datos no hay nada que afirmar sobre el contenido, pero un nombre de
campo mal escrito, un método pedido a una lista o un import circular saltan igual. Es barato y
cubre justo el hueco que el `except` tapaba.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from football import asistente_consultas as consultas
from football.models import Club, Team


class ConsultasDelAsistenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user(username="entrenador", password="x")
        club = Club.objects.create(name="Club de prueba")
        cls.equipo = Team.objects.create(name="Equipo de prueba", club=club)

    def test_cada_consulta_se_ejecuta_sin_romperse(self):
        """Cada pareja (reconoce, contesta) del catálogo, con una frase que la despierta."""
        frases = {
            "es_pregunta_asistencia": "quién no vino el martes",
            "es_pregunta_tareas_de_sesion": "qué tareas tiene la sesión del martes",
            "es_pregunta_cuantas_sesiones": "cuántas sesiones llevo esta semana",
            "es_pregunta_entrenos_semana": "cuándo entrenamos esta semana",
            "es_pregunta_minutos": "quién ha jugado menos minutos",
            "es_pregunta_balance": "cuántos partidos hemos ganado",
            "es_pregunta_sancionados": "quién está sancionado",
            "es_pregunta_cumpleanos": "quién cumple años este mes",
            "es_pregunta_sin_ficha": "qué jugadores no tienen ficha",
            "es_pregunta_jugador": "ficha de un jugador",
            "es_pregunta_convocatoria": "a quién tengo convocado",
            "es_pregunta_sin_evaluar": "qué jugadores llevo sin evaluar",
            "es_pregunta_rival": "cómo es el próximo rival",
            "es_pregunta_ultimo_partido": "cómo quedó el último partido",
            "es_pregunta_proximo_partido": "contra quién jugamos",
            "es_pregunta_videos": "qué vídeos tengo",
            "es_pregunta_clasificacion": "cómo va la clasificación",
            "es_pregunta_goleador": "quién es el máximo goleador",
            "es_pregunta_cuantas_tareas": "cuántas tareas tengo en la biblioteca",
        }
        sin_frase = [r.__name__ for r, _ in consultas.CONSULTAS if r.__name__ not in frases]
        self.assertEqual(sin_frase, [], "hay consultas nuevas sin frase de prueba aquí")

        for reconoce, contesta in consultas.CONSULTAS:
            frase = frases[reconoce.__name__]
            with self.subTest(consulta=reconoce.__name__):
                self.assertTrue(reconoce(frase), "la frase de prueba ya no la despierta")
                # Sin try/except a propósito: si esto revienta, el test tiene que enterarse.
                # Es justo lo que `responder()` esconde en producción.
                salida = contesta(frase, self.equipo)
                self.assertIsInstance(salida, dict)
                self.assertTrue(str(salida.get("message") or "").strip())

    def test_una_orden_no_la_contesta_una_consulta(self):
        """Una orden con el pronombre pegado tiene que leerse como orden.

        «quítale la convocatoria a Ariel» se contestaba con la LISTA de convocados, porque
        "quita" se reconocía y "quitale" no. Desde fuera eso se lee como un "hecho", que es el
        peor fallo posible en algo que escribe en la ficha de alguien.
        """
        from football.asistente_rapido import detectar_intencion

        for frase in ("quítale la convocatoria a Ariel Palo", "ponle una nota al partido",
                      "sácale del once", "márcale como ausente"):
            with self.subTest(frase=frase):
                self.assertEqual(detectar_intencion(frase)[0], "orden")

        # Y al revés: el pronombre de primera persona NO convierte en orden lo que es una
        # petición de ir a un sitio.
        for frase in ("ponme donde los entrenos", "llévame a entrenamientos"):
            with self.subTest(frase=frase):
                self.assertNotEqual(detectar_intencion(frase)[0], "orden")

        # Ninguna pregunta del catálogo puede leerse como orden: si se leyera, dejaría de
        # contestarse y caería al guardián.
        for frase in ("quién está sancionado", "a quién tengo convocado",
                      "cuántos partidos hemos ganado", "qué jugadores llevo sin evaluar"):
            with self.subTest(frase=frase):
                self.assertNotEqual(detectar_intencion(frase)[0], "orden")

    def test_ninguna_frase_se_la_queda_la_consulta_equivocada(self):
        """El orden del catálogo importa: la primera que reconoce se lleva la pregunta."""
        esperado = {
            "cuántos partidos hemos ganado": "es_pregunta_balance",
            "cómo quedó el último partido": "es_pregunta_ultimo_partido",
            "cuándo entrenamos esta semana": "es_pregunta_entrenos_semana",
            "quién está sancionado": "es_pregunta_sancionados",
            "quién no vino el martes": "es_pregunta_asistencia",
        }
        for frase, nombre in esperado.items():
            with self.subTest(frase=frase):
                primera = next((r.__name__ for r, _ in consultas.CONSULTAS if r(frase)), "")
                self.assertEqual(primera, nombre)
