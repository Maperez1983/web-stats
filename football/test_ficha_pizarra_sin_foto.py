"""Una foto de carnet no puede acabar de ficha en una pizarra.

Medido en produccion el 2026-08-06 con el senior: 12 de 25 jugadores no tienen recorte,
y cada pizarra estropeaba su foto de una forma distinta.

  - 11 inicial: uno salia como un rectangulo APAISADO (523x416) con la verja de su casa de
    fondo, ocupando el doble de ancho que sus companieros; otro, con el recuadro negro de su
    foto detras de la figura.
  - Planteamiento: ese mismo jugador salia como un disco liso SIN CARA, porque el recorte
    circular de 62 px le caia en la camiseta.

La causa era comun: `resolve_player_avatar_url` devuelve "" para un adulto sin avatar generado
y cada pantalla caia por su cuenta en la foto subida. Ahora hay una unica puerta,
`resolve_player_board_avatar_url`, que SIEMPRE devuelve una figura.
"""
from django.test import SimpleTestCase, TestCase

from football.models import Player, Team


class PuertaUnicaDeLaFichaTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Pruebas Pizarra")

    def _jugador(self, **extra):
        return Player.objects.create(team=self.team, name="Adulto Sin Avatar", number=6, **extra)

    def test_un_adulto_sin_avatar_recibe_figura_generica_y_no_vacio(self):
        from football.views import resolve_player_avatar_url, resolve_player_board_avatar_url

        p = self._jugador()
        # El resolver de siempre se desentiende del adulto: ese "" es lo que empujaba a la foto.
        self.assertEqual(resolve_player_avatar_url(p), "")
        url = resolve_player_board_avatar_url(p)
        self.assertTrue(url, "la ficha de pizarra se ha quedado sin imagen: volvera a caer en la foto")
        self.assertIn("coach_roster_avatars/library/", url)

    def test_nunca_devuelve_la_foto_del_jugador(self):
        from football.views import resolve_player_board_avatar_url

        p = self._jugador()
        url = resolve_player_board_avatar_url(p)
        self.assertNotIn("/photo/", url)
        self.assertNotIn("/media/", url)


class FuenteDeLaFichaEnLasPizarrasTests(SimpleTestCase):
    """Las pizarras tienen que pedir la figura, no la foto. Se mira el fuente porque el
    recorrido completo necesita storage y foto subida, y lo que se rompio fue el ORDEN."""

    def test_planteamiento_y_jugadas_piden_la_figura(self):
        from pathlib import Path

        src = (Path(__file__).resolve().parent / "tactical_plan_views.py").read_text(encoding="utf-8")
        self.assertIn("resolve_player_board_avatar_url", src)
        self.assertNotIn(
            "foto = resolve_player_photo_url(request, player)",
            src,
            "_foto_de vuelve a pedir la foto ANTES que la figura: el jugador sin recorte "
            "volvera a salir como un disco liso sin cara",
        )

    def test_el_dorsal_de_dos_cifras_cabe_en_la_chapita(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parent / "templates" / "football" / "coach_initial_eleven.html"
        ).read_text(encoding="utf-8")
        bloque = html.split(".xi-chip--figura .xi-chip-num {", 1)[1].split("}", 1)[0]
        self.assertNotIn(
            "width: 24px;",
            bloque.replace("min-width: 24px;", ""),
            "vuelve el ancho fijo: el 11 se parte en un '1' y otro '1'",
        )
        self.assertIn("white-space: nowrap;", bloque)
