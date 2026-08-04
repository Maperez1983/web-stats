"""Tareas de un libro dentro de la biblioteca, con ficha y pizarra editable.

Lo que exige el usuario es la superficie EDITABLE: una foto del ejercicio pegada en la ficha no
sirve. Como los gráficos del libro son imágenes rasterizadas, el dibujo se reconstruye fuera y
entra como objetos del editor; aquí se fija que lleguen a `tactical_layout` y no se pierdan.

Y que la metodología acabe en las columnas por las que se filtra la biblioteca, que no se
escriben a mano: las deriva SessionTask.save() desde el JSON.
"""

from django.test import TestCase

from football.library_repositories import is_library_microcycle
from football.models import (
    AiTrainerTokenWeight,
    SessionTask,
    SessionTaskCollection,
    SessionTaskCollectionItem,
    Team,
)
from football.task_book_import import importar_fichas

FICHA = {
    'titulo': '3 c 3 en espacio reducido',
    'descripcion': 'Tres contra tres en espacio reducido con porterías.',
    'reglas': 'Al completar 4 pases se abre el espacio para atacar a una portería.',
    'comportamientos': 'Resolución de situaciones en espacio muy reducido. Lucha uno contra uno.',
    'bioenergetico': 'Acciones de lucha cuerpo a cuerpo de corta duración.',
    'consideraciones': 'Ajustar los espacios a las características de los jugadores.',
    'momento': 'posesion',
    'estructura': 'condicional',
    'contenido': 'fisico',
    'situacion': 'igualdad',
    'minutos': 12,
    'fuente': 'Pol (2011), p. 187',
    'objetos': [
        {'type': 'circle', 'left': 100, 'top': 120, 'data': {'kind': 'player_home', 'label': ''}},
        {'type': 'circle', 'left': 300, 'top': 120, 'data': {'kind': 'player_away', 'label': ''}},
        {'type': 'rect', 'left': 60, 'top': 60, 'data': {'kind': 'zone', 'label': 'Zona'}},
    ],
}


class ImportarTareasDeLibroTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='C.D. Ejemplo', slug='cd-ejemplo-libro', is_primary=True)

    def test_la_tarea_entra_con_su_ficha(self):
        resumen = importar_fichas(self.team, [FICHA])
        self.assertEqual(resumen['creadas'], ['3 c 3 en espacio reducido'])
        tarea = SessionTask.objects.get(title='3 c 3 en espacio reducido')
        self.assertIn('espacio reducido', tarea.objective)
        self.assertIn('4 pases', tarea.confrontation_rules)
        self.assertIn('uno contra uno', tarea.coaching_points)
        self.assertEqual(tarea.duration_minutes, 12)

    def test_el_dibujo_queda_editable_no_pegado(self):
        importar_fichas(self.team, [FICHA])
        tarea = SessionTask.objects.get(title=FICHA['titulo'])
        objetos = tarea.tactical_layout['meta']['graphic_editor']['canvas_state']['objects']
        self.assertEqual(len(objetos), 3)
        self.assertEqual(objetos[0]['data']['kind'], 'player_home')

    def test_la_metodologia_llega_a_las_columnas_de_filtrado(self):
        """Esas columnas NO se escriben a mano: las deriva save() desde el JSON."""
        importar_fichas(self.team, [FICHA])
        tarea = SessionTask.objects.get(title=FICHA['titulo'])
        self.assertEqual(tarea.game_moment, 'offensive_organization')
        self.assertEqual(tarea.structure_periodization, 'conditional')
        self.assertEqual(tarea.content_domain, 'physical')

    def test_va_a_su_propia_estanteria(self):
        importar_fichas(self.team, [FICHA], coleccion='Tareas importadas')
        coleccion = SessionTaskCollection.objects.get(team=self.team, name='Tareas importadas')
        self.assertEqual(SessionTaskCollectionItem.objects.filter(collection=coleccion).count(), 1)

    def test_queda_dicho_de_donde_viene(self):
        importar_fichas(self.team, [FICHA])
        tarea = SessionTask.objects.get(title=FICHA['titulo'])
        self.assertIn('Pol (2011)', tarea.notes)
        self.assertEqual(tarea.tactical_layout['meta']['source'], 'Pol (2011), p. 187')

    def test_importar_dos_veces_no_duplica(self):
        importar_fichas(self.team, [FICHA])
        resumen = importar_fichas(self.team, [FICHA])
        self.assertEqual(resumen['creadas'], [])
        self.assertEqual(resumen['ya_estaban'], [FICHA['titulo']])
        self.assertEqual(SessionTask.objects.filter(title=FICHA['titulo']).count(), 1)

    def test_cae_en_la_biblioteca_y_no_en_una_sesion_de_verdad(self):
        importar_fichas(self.team, [FICHA])
        tarea = SessionTask.objects.get(title=FICHA['titulo'])
        self.assertTrue(is_library_microcycle(tarea.session.microcycle))

    def test_importar_no_ensucia_el_aprendizaje(self):
        """Entrar en la biblioteca no es entrenarla: el recomendador no debe aprender de esto."""
        importar_fichas(self.team, [FICHA])
        self.assertEqual(AiTrainerTokenWeight.objects.count(), 0)

    def test_la_simulacion_no_escribe(self):
        resumen = importar_fichas(self.team, [FICHA], escribir=False)
        self.assertEqual(resumen['creadas'], [FICHA['titulo']])
        self.assertEqual(SessionTask.objects.count(), 0)

    def test_una_ficha_sin_titulo_se_descarta_sin_romper_el_lote(self):
        resumen = importar_fichas(self.team, [{'descripcion': 'sin título'}, FICHA])
        self.assertEqual(resumen['creadas'], [FICHA['titulo']])
        self.assertEqual(len(resumen['descartadas']), 1)

    def test_lo_que_no_se_sabe_no_se_inventa(self):
        """Si el libro no dice el momento de juego, la columna se queda vacía: estas columnas
        alimentan los filtros, y un dato inventado es peor que ninguno."""
        importar_fichas(self.team, [dict(FICHA, momento='', estructura='', contenido='')])
        tarea = SessionTask.objects.get(title=FICHA['titulo'])
        self.assertEqual(tarea.game_moment, '')
        self.assertEqual(tarea.structure_periodization, '')
