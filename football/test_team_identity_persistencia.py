"""El equipo rival persiste de un año para otro: el grupo dice dónde juega, no quién es."""
from django.test import TestCase

from football.models import Competition, Group, Season, Team, resolve_or_create_team


class EquipoPersisteEntreTemporadas(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga Senior", slug="liga-senior", region="Andalucia")
        self.temporada_vieja = Season.objects.create(competition=self.comp, name="2025/2026")
        self.temporada_nueva = Season.objects.create(competition=self.comp, name="2026/2027", is_current=True)
        self.grupo_viejo = Group.objects.create(season=self.temporada_vieja, name="Grupo 2", slug="g2-2526")
        self.grupo_nuevo = Group.objects.create(season=self.temporada_nueva, name="Grupo 2", slug="g2-2627")

    def test_el_mismo_club_no_se_duplica_al_cambiar_de_temporada(self):
        viejo, creado = resolve_or_create_team(
            name="C.D. Rincón", group=self.grupo_viejo, defaults={"category": "Senior"}
        )
        self.assertTrue(creado)
        nuevo, creado_otra_vez = resolve_or_create_team(
            name="CD Rincon", group=self.grupo_nuevo, defaults={"category": "Senior"}
        )
        self.assertFalse(creado_otra_vez, "el mismo club no puede nacer otra vez cada temporada")
        self.assertEqual(viejo.id, nuevo.id)
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.group_id, self.grupo_nuevo.id, "debe pasar a jugar en el grupo de este año")
        self.assertEqual(Team.objects.filter(name_key=viejo.name_key).count(), 1)

    def test_dos_categorias_del_mismo_club_siguen_siendo_dos_equipos(self):
        senior, _ = resolve_or_create_team(
            name="C.D. Rincón", group=self.grupo_nuevo, defaults={"category": "Senior"}
        )
        cadete, creado = resolve_or_create_team(
            name="C.D. Rincón", group=self.grupo_viejo, defaults={"category": "Cadete"}
        )
        self.assertTrue(creado, "el cadete del mismo club NO es el senior")
        self.assertNotEqual(senior.id, cadete.id)
