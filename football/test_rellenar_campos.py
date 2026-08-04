"""Rellenar campo y dirección en lote, sin pisar lo que ya hay.

El dato de la federación completa huecos; NO manda sobre lo que el club haya escrito a mano.
Y va en un solo lote a propósito: hacerlo por el formulario del admin equipo por equipo son
más de cien peticiones caras y tumba el servidor (pasó el 2026-08-04, dos veces).
"""

from django.test import TestCase

from football.models import Team
from football.team_venue_fill import rellenar_campos


class RellenarCamposTests(TestCase):
    def setUp(self):
        self.vacio = Team.objects.create(name='C.D. Sin Campo', slug='cd-sin-campo')
        self.lleno = Team.objects.create(
            name='C.D. Con Campo',
            slug='cd-con-campo',
            home_stadium='El de siempre',
            home_stadium_address='Calle Mía, 1',
        )
        self.por_id = {self.vacio.id: self.vacio, self.lleno.id: self.lleno}

    def test_rellena_el_hueco(self):
        resumen = rellenar_campos(self.por_id, [
            {'id': self.vacio.id, 'campo': 'Municipal de Ejemplo', 'direccion': 'Av. del Test, 3'},
        ])
        self.vacio.refresh_from_db()
        self.assertEqual(self.vacio.home_stadium, 'Municipal de Ejemplo')
        self.assertEqual(self.vacio.home_stadium_address, 'Av. del Test, 3')
        self.assertEqual(len(resumen['actualizados']), 1)

    def test_no_pisa_lo_que_ya_estaba(self):
        rellenar_campos(self.por_id, [
            {'id': self.lleno.id, 'campo': 'Otro Campo', 'direccion': 'Otra Calle, 9'},
        ])
        self.lleno.refresh_from_db()
        self.assertEqual(self.lleno.home_stadium, 'El de siempre')
        self.assertEqual(self.lleno.home_stadium_address, 'Calle Mía, 1')

    def test_sobrescribir_solo_si_se_pide(self):
        rellenar_campos(self.por_id, [
            {'id': self.lleno.id, 'campo': 'Otro Campo'},
        ], sobrescribir=True)
        self.lleno.refresh_from_db()
        self.assertEqual(self.lleno.home_stadium, 'Otro Campo')

    def test_rellena_el_hueco_aunque_otro_dato_ya_este(self):
        """Tiene campo pero no dirección: la dirección debe entrar."""
        equipo = Team.objects.create(name='C.D. Medio', slug='cd-medio', home_stadium='Su campo')
        resumen = rellenar_campos({equipo.id: equipo}, [
            {'id': equipo.id, 'campo': 'Otro', 'direccion': 'Calle Nueva, 5'},
        ])
        equipo.refresh_from_db()
        self.assertEqual(equipo.home_stadium, 'Su campo')  # intacto
        self.assertEqual(equipo.home_stadium_address, 'Calle Nueva, 5')  # rellenado
        self.assertEqual(len(resumen['actualizados']), 1)

    def test_simulacion_no_escribe(self):
        resumen = rellenar_campos(self.por_id, [
            {'id': self.vacio.id, 'campo': 'Municipal de Ejemplo'},
        ], escribir=False)
        self.vacio.refresh_from_db()
        self.assertEqual(self.vacio.home_stadium, '')
        self.assertEqual(len(resumen['actualizados']), 1)

    def test_id_desconocido_no_rompe(self):
        resumen = rellenar_campos(self.por_id, [{'id': 999999, 'campo': 'X'}])
        self.assertEqual(resumen['sin_equipo'], [999999])

    def test_entradas_basura_no_rompen(self):
        resumen = rellenar_campos(self.por_id, ['no soy un dict', None, {'sin': 'id'}])
        self.assertEqual(resumen['actualizados'], [])

    def test_recorta_a_lo_que_cabe_en_el_campo(self):
        resumen = rellenar_campos(self.por_id, [
            {'id': self.vacio.id, 'campo': 'X' * 500},
        ])
        self.vacio.refresh_from_db()
        self.assertEqual(len(self.vacio.home_stadium), 200)
        self.assertEqual(len(resumen['actualizados']), 1)

    def test_valor_vacio_no_borra_lo_que_hay(self):
        rellenar_campos(self.por_id, [{'id': self.lleno.id, 'campo': '', 'direccion': '   '}])
        self.lleno.refresh_from_db()
        self.assertEqual(self.lleno.home_stadium, 'El de siempre')
