"""Un club escrito de dos formas es UN equipo, no dos fichas.

Cada fuente escribe el mismo club a su manera: la federación manda "Castejon" y laPreferente
"E.F. de Vélez Francisco Castejón". Como el sembrado de rivales emparejaba por nombre exacto,
el mismo club entraba dos veces y quedaban fichas duplicadas (Castejón, Santa Cruz, Rincón,
Alhaurín, La Cala, Nerja). Fusionarlas no bastaba: la siguiente sincronización las repetía.

Aparte, aquí se fija que el equipo "de sistema" (el repositorio de recursos de la pizarra) NO
se trate como un club: parece basura en los listados y borrarlo se lleva el catálogo global.
"""

from django.test import TestCase

from football.calendar_sync_services import _resolve_opponent
from football.models import (
    Team,
    TeamNameAlias,
    is_system_team,
    merge_teams,
    register_team_alias,
    resolve_or_create_team,
    team_by_alias,
)
from football.rival_seed_services import seed_rivals_from_standings

NOMBRE_LARGO = 'E.F. de Vélez Francisco Castejón'
NOMBRE_CORTO = 'Castejon'


class AliasDeEquipoTests(TestCase):
    def setUp(self):
        self.castejon = Team.objects.create(name=NOMBRE_LARGO, slug='ef-velez-francisco-castejon')

    def test_alias_encuentra_el_equipo_escrito_de_otra_forma(self):
        register_team_alias(self.castejon, NOMBRE_CORTO, source='universo')
        self.assertEqual(team_by_alias(NOMBRE_CORTO), self.castejon)
        # Normaliza igual que name_key: acentos, puntos y mayúsculas dan igual.
        self.assertEqual(team_by_alias('CASTEJÓN'), self.castejon)

    def test_sin_alias_no_hay_falso_positivo(self):
        self.assertIsNone(team_by_alias(NOMBRE_CORTO))
        self.assertIsNone(team_by_alias(''))
        self.assertIsNone(team_by_alias(None))

    def test_no_se_registra_un_alias_que_es_el_nombre_real_de_otro_equipo(self):
        otro = Team.objects.create(name=NOMBRE_CORTO, slug='castejon-otro')
        self.assertIsNone(register_team_alias(self.castejon, NOMBRE_CORTO))
        self.assertEqual(Team.objects.filter(pk=otro.pk).count(), 1)

    def test_una_grafia_no_puede_apuntar_a_dos_equipos(self):
        otro = Team.objects.create(name='C.D. Otro Club', slug='cd-otro-club')
        self.assertIsNotNone(register_team_alias(self.castejon, NOMBRE_CORTO))
        self.assertIsNone(register_team_alias(otro, NOMBRE_CORTO))
        self.assertEqual(TeamNameAlias.objects.filter(alias_key='castejon').count(), 1)

    def test_resolve_or_create_no_crea_ficha_si_hay_alias(self):
        register_team_alias(self.castejon, NOMBRE_CORTO, source='universo')
        antes = Team.objects.count()
        team, created = resolve_or_create_team(name=NOMBRE_CORTO)
        self.assertFalse(created)
        self.assertEqual(team, self.castejon)
        self.assertEqual(Team.objects.count(), antes)

    def test_la_fusion_deja_escrito_el_alias(self):
        suelto = Team.objects.create(name=NOMBRE_CORTO, slug='castejon', short_name=NOMBRE_CORTO)
        merge_teams(self.castejon, suelto)
        self.assertFalse(Team.objects.filter(name=NOMBRE_CORTO).exists())
        self.assertEqual(team_by_alias(NOMBRE_CORTO), self.castejon)

    def test_tras_fusionar_la_siguiente_sincronizacion_ya_no_lo_recrea(self):
        """El fallo real: limpiar el duplicado no duraba nada."""
        suelto = Team.objects.create(name=NOMBRE_CORTO, slug='castejon', short_name=NOMBRE_CORTO)
        merge_teams(self.castejon, suelto)
        equipos = Team.objects.count()
        propio = Team.objects.create(name='C.D. Benagalbón', slug='cd-benagalbon-alias', is_primary=True)
        seed_rivals_from_standings(propio, [{'full_name': NOMBRE_CORTO}])
        self.assertEqual(Team.objects.filter(name=NOMBRE_CORTO).count(), 0)
        # Sólo se sumó el equipo primario que acabamos de crear, ningún rival nuevo.
        self.assertEqual(Team.objects.count(), equipos + 1)

    def test_el_sembrado_sigue_creando_a_los_rivales_de_verdad(self):
        propio = Team.objects.create(name='C.D. Benagalbón', slug='cd-benagalbon-alias2', is_primary=True)
        resultado = seed_rivals_from_standings(propio, [{'full_name': 'C.D. Rival Nuevo'}])
        self.assertEqual(resultado['created'], 1)
        self.assertTrue(Team.objects.filter(name='C.D. Rival Nuevo').exists())

    def test_el_sembrado_reconoce_al_club_ya_existente_por_nombre_normalizado(self):
        """Misma grafía salvo acentos y puntuación: es el mismo club, no uno nuevo."""
        propio = Team.objects.create(name='C.D. Benagalbón', slug='cd-benagalbon-alias3', is_primary=True)
        resultado = seed_rivals_from_standings(propio, [{'full_name': 'EF de Velez Francisco Castejon'}])
        self.assertEqual(resultado['created'], 0)
        self.assertEqual(Team.objects.filter(name__icontains='Castej').count(), 1)

    def test_el_calendario_usa_el_alias_en_vez_de_crear_rival(self):
        register_team_alias(self.castejon, NOMBRE_CORTO, source='universo')
        propio = Team.objects.create(name='C.D. Benagalbón', slug='cd-benagalbon-alias4', is_primary=True)
        antes = Team.objects.count()
        rival = _resolve_opponent(propio, None, NOMBRE_CORTO, write=True)
        self.assertEqual(rival, self.castejon)
        self.assertEqual(Team.objects.count(), antes)


class EquipoDeSistemaTests(TestCase):
    """El repositorio de recursos de la pizarra no es un club.

    Se llama PIZARRA y no tiene grupo, categoría, partidos ni jugadores, así que en el admin
    se lee exactamente igual que una ficha basura. Lo es tan poco que borrarlo arrastra por
    cascada los iconos del catálogo global (PdfGraphicAsset.team = CASCADE).
    """

    def setUp(self):
        self.sistema = Team.objects.filter(slug='pizarra').first() or Team.objects.create(
            name='PIZARRA', slug='pizarra'
        )

    def test_se_reconoce_el_equipo_de_sistema(self):
        self.assertTrue(is_system_team(self.sistema))
        club = Team.objects.create(name='C.D. Pizarra Atlético C.F.', slug='cd-pizarra-atletico-cf')
        self.assertFalse(is_system_team(club))
        self.assertFalse(is_system_team(None))

    def test_no_se_fusiona_el_repositorio_del_sistema_con_un_club(self):
        club = Team.objects.create(name='C.D. Pizarra Atlético C.F.', slug='cd-pizarra-atletico-cf-2')
        merge_teams(club, self.sistema)
        self.assertTrue(Team.objects.filter(slug='pizarra').exists())

    def test_tampoco_al_reves(self):
        club = Team.objects.create(name='C.D. Pizarra Atlético C.F.', slug='cd-pizarra-atletico-cf-3')
        merge_teams(self.sistema, club)
        self.assertTrue(Team.objects.filter(pk=club.pk).exists())
