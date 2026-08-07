"""El catálogo de escudos tiene que mirar la base, no sólo los ficheros del Universo."""
from django.test import TestCase

from football import team_media_services
from football.models import Competition, Group, Season, Team


class EscudosDeLaClasificacionTests(TestCase):
    def setUp(self):
        comp = Competition.objects.create(name="Liga E", slug="liga-e", region="Andalucia")
        temporada = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        self.grupo = Group.objects.create(season=temporada, name="G", slug="g-e")
        # El memo de la función guarda el catálogo de ficheros entre llamadas.
        team_media_services.build_team_crest_lookup._memo = None

    def _catalogo(self):
        return team_media_services.build_team_crest_lookup(load_snapshot_func=lambda: {})

    def test_el_escudo_guardado_en_la_ficha_del_equipo_entra_en_el_catalogo(self):
        """Sin esto la clasificación de la home salía sin un solo escudo: los ficheros del
        Universo no viajan en el despliegue y eran la única fuente."""
        rival = Team.objects.create(
            name="C.D. Casabermeja", slug="casabermeja-e", group=self.grupo,
            crest_url="https://www.lapreferente.com/imagenes/escudos/uno.png",
        )
        catalogo = self._catalogo()
        clave = team_media_services._normalize_team_lookup_key(rival.name)
        self.assertIn(clave, catalogo)
        self.assertTrue(catalogo[clave].endswith("uno.png"))

    def test_tambien_vale_el_escudo_subido_como_fichero(self):
        """El del propio club suele estar subido, no enlazado: por eso faltaba justo el tuyo."""
        propio = Team.objects.create(name="Benagalbón Senior", slug="ben-sr-e", group=self.grupo)
        propio.crest_image.name = "team-crests/escudo.png"
        propio.save(update_fields=["crest_image"])
        catalogo = self._catalogo()
        clave = team_media_services._normalize_team_lookup_key(propio.name)
        self.assertIn(clave, catalogo, "el escudo subido como fichero también cuenta")

    def test_un_equipo_sin_escudo_no_ensucia_el_catalogo(self):
        Team.objects.create(name="Sin Escudo C.F.", slug="sin-escudo-e", group=self.grupo)
        catalogo = self._catalogo()
        clave = team_media_services._normalize_team_lookup_key("Sin Escudo C.F.")
        self.assertNotIn(clave, catalogo)
