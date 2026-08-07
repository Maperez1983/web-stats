"""La marca del producto se pinta UNA vez y con la misma pieza en todas las pantallas.

Antes habia dos componentes compitiendo -el logotipo horizontal de la portada y la
pastilla oscura de 94px de la barra- y cuatro plantillas con su propia copia a mano.
El resultado era que ninguna pantalla llevaba el logo igual que la de al lado.
"""
import re
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

PLANTILLAS = Path(__file__).resolve().parent / "templates" / "football"


class MarcaUnicaTests(SimpleTestCase):
    def _fuente(self, nombre):
        return (PLANTILLAS / nombre).read_text(encoding="utf-8")

    def test_el_bloque_de_marca_lleva_icono_y_rotulo(self):
        html = render_to_string("football/includes/_marca_2j.html", {})
        self.assertIn("marca2j-icono", html)
        self.assertIn("2j-icon", html, "el icono es la pieza comun del sistema")
        self.assertIn("Segunda Jugada", html)
        self.assertIn("2J Club", html, "sin sufijo, la marca es la del club")

    def test_el_sufijo_distingue_la_zona_de_jugador(self):
        html = render_to_string("football/includes/_marca_2j.html", {"marca_sufijo": "2J Player"})
        self.assertIn("2J Player", html)
        self.assertNotIn("2J Club", html)

    def test_nadie_vuelve_a_pintar_el_logotipo_horizontal_dentro_del_producto(self):
        """2j-mark.svg trae el rotulo DIBUJADO dentro, en colores de fondo oscuro: dentro
        de la aplicacion (que tiene modo claro) desaparecia y ademas salia repetido."""
        culpables = []
        for ruta in PLANTILLAS.rglob("*.html"):
            if "images/2j-mark.svg" in ruta.read_text(encoding="utf-8"):
                culpables.append(ruta.name)
        # Las pantallas publicas (login, alta, invitacion, landing) van siempre sobre
        # fondo oscuro y ahi el logotipo horizontal es la pieza correcta.
        permitidas = {
            "product_landing.html",
            "invitation_accept.html",
            "platform_workspace_detail.html",
            "task_studio_home.html",
        }
        self.assertEqual(sorted(set(culpables) - permitidas), [])

    def test_las_pantallas_de_jugador_no_pintan_dos_marcas(self):
        """player_dashboard y player_detail escribian su propio rotulo y ademas incluian
        la barra con el logo: se veian dos marcas seguidas."""
        for nombre in ("player_dashboard.html", "player_detail.html"):
            fuente = self._fuente(nombre)
            self.assertNotIn(
                "product-brand-strip",
                fuente,
                f"{nombre} vuelve a montar su propia marca en vez de usar el bloque comun",
            )

    def test_la_portada_usa_el_bloque_comun(self):
        fuente = self._fuente("coach_overview.html")
        self.assertIn("includes/_marca_2j.html", fuente)

    def test_la_barra_global_usa_el_bloque_comun(self):
        fuente = self._fuente("includes/dragon_nav.html")
        self.assertIn("includes/_marca_2j.html", fuente)
        self.assertNotIn(
            "2j-icon.svg",
            fuente,
            "la barra ya no pinta el icono suelto: lo hace el bloque de marca",
        )

    def test_el_contenedor_de_la_barra_no_vuelve_a_ser_una_pastilla_de_94px(self):
        css = (
            Path(__file__).resolve().parent.parent
            / "static"
            / "football"
            / "css"
            / "commercial.css"
        ).read_text(encoding="utf-8")
        bloque = re.search(r"body\.prod-commercial \.dragon-nav \{(.*?)\}", css, re.S)
        self.assertIsNotNone(bloque)
        self.assertNotIn("94px", bloque.group(1))
        self.assertIn(".marca2j", css, "el bloque de marca necesita su estilo comun")
