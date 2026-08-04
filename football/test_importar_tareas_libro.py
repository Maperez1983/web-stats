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


class ZonasQueNoTapanElCampoTests(TestCase):
    """Un rect sin `fill` lo pinta el lienzo NEGRO Y OPACO: tapa el campo y las fichas.

    Pasó con las dos primeras tareas del libro (2026-08-04): al abrir el editor sólo se veía un
    rectángulo negro. El estilo lo pone el importador, no quien manda el lote.
    """

    def setUp(self):
        self.team = Team.objects.create(name='C.D. Zonas', slug='cd-zonas', is_primary=True)

    def _objetos_de(self, titulo='Con zona'):
        tarea = SessionTask.objects.get(title=titulo)
        return tarea.tactical_layout['meta']['graphic_editor']['canvas_state']['objects']

    def test_la_zona_entra_translucida_y_con_borde(self):
        importar_fichas(self.team, [{
            'titulo': 'Con zona',
            'objetos': [{'type': 'rect', 'left': 10, 'top': 10, 'data': {'kind': 'zone'}}],
        }])
        zona = self._objetos_de()[0]
        self.assertIn('rgba', zona['fill'])
        self.assertNotEqual(zona['fill'], '')
        self.assertTrue(zona.get('stroke'))

    def test_no_se_pisa_el_estilo_que_ya_venga(self):
        importar_fichas(self.team, [{
            'titulo': 'Con zona',
            'objetos': [{'type': 'rect', 'fill': 'rgba(255,0,0,0.2)', 'data': {'kind': 'zone'}}],
        }])
        self.assertEqual(self._objetos_de()[0]['fill'], 'rgba(255,0,0,0.2)')

    def test_cualquier_rectangulo_suelto_tampoco_sale_negro(self):
        importar_fichas(self.team, [{
            'titulo': 'Con zona',
            'objetos': [{'type': 'rect', 'data': {'kind': 'otra_cosa'}}],
        }])
        self.assertTrue(self._objetos_de()[0].get('fill'))

    def test_reimportar_corregido_actualiza_el_dibujo(self):
        importar_fichas(self.team, [{'titulo': 'Con zona', 'objetos': [{'type': 'rect', 'data': {'kind': 'zone'}}]}])
        resumen = importar_fichas(self.team, [{
            'titulo': 'Con zona',
            'descripcion': 'corregida',
            'objetos': [{'type': 'circle', 'left': 5, 'top': 5, 'data': {'kind': 'ball'}}],
        }], actualizar=True)
        self.assertEqual(resumen['actualizadas'], ['Con zona'])
        self.assertEqual(self._objetos_de()[0]['data']['kind'], 'ball')
        self.assertEqual(SessionTask.objects.get(title='Con zona').objective, 'corregida')


class PiezasQueSeVenTests(TestCase):
    """El lienzo no deduce nada de `data.kind`.

    Un círculo sin `radius` se dibuja de tamaño cero y una ficha sin contenido es un envoltorio
    vacío: las dos primeras tareas del libro entraron así y el campo salía sin jugadores, conos
    ni balón (2026-08-04).
    """

    def setUp(self):
        self.team = Team.objects.create(name='C.D. Piezas', slug='cd-piezas', is_primary=True)

    def _objetos(self, objetos):
        importar_fichas(self.team, [{'titulo': 'Piezas', 'objetos': objetos}])
        tarea = SessionTask.objects.get(title='Piezas')
        return tarea.tactical_layout['meta']['graphic_editor']['canvas_state']['objects']

    def test_la_ficha_de_jugador_lleva_su_disco_dentro(self):
        o = self._objetos([{'type': 'group', 'left': 100, 'top': 100, 'data': {'kind': 'player_local'}}])[0]
        self.assertEqual(o['type'], 'group')
        self.assertTrue(o['objects'])
        disco = o['objects'][0]
        self.assertEqual(disco['type'], 'circle')
        self.assertGreater(disco['radius'], 0)
        self.assertTrue(disco['fill'])

    def test_local_y_rival_no_son_del_mismo_color(self):
        local = self._objetos([{'type': 'group', 'data': {'kind': 'player_local'}}])[0]
        SessionTask.objects.all().delete()
        rival = self._objetos([{'type': 'group', 'data': {'kind': 'player_rival'}}])[0]
        self.assertNotEqual(local['objects'][0]['fill'], rival['objects'][0]['fill'])

    def test_el_dorsal_se_dibuja_encima(self):
        o = self._objetos([{'type': 'group', 'data': {'kind': 'player_local', 'label': 'C'}}])[0]
        textos = [h for h in o['objects'] if h.get('type') == 'text']
        self.assertEqual(textos[0]['text'], 'C')

    def test_el_cono_tiene_tamano(self):
        o = self._objetos([{'type': 'circle', 'left': 50, 'top': 50, 'data': {'kind': 'cone'}}])[0]
        self.assertGreater(o['radius'], 0)
        self.assertTrue(o['fill'])

    def test_el_balon_tiene_tamano(self):
        o = self._objetos([{'type': 'circle', 'data': {'kind': 'ball'}}])[0]
        self.assertGreater(o['radius'], 0)

    def test_ningun_circulo_se_queda_sin_radio(self):
        o = self._objetos([{'type': 'circle', 'data': {'kind': 'lo_que_sea'}}])[0]
        self.assertGreater(o['radius'], 0)

    def test_se_respeta_la_posicion_que_se_pide(self):
        o = self._objetos([{'type': 'group', 'left': 321, 'top': 123, 'data': {'kind': 'player_rival'}}])[0]
        self.assertEqual(o['left'], 321)
        self.assertEqual(o['top'], 123)
