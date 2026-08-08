"""La barra "Zona Partido" tiene que leerse en los tres temas.

Fijaba un fondo oscuro a mano y escribia con los colores del TEMA: en modo claro el
rival, "Lista guardada" y los cuatro pasos salian azul marino sobre azul marino
(contraste medido 1.11; lo legible empieza en 4.5).
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

BARRA = (
    Path(__file__).resolve().parent
    / "templates"
    / "football"
    / "includes"
    / "matchday_flow_bar.html"
)


def _luminancia(hex_color):
    hex_color = hex_color.lstrip("#")
    canales = [int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lineal = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _contraste(uno, otro):
    a, b = _luminancia(uno), _luminancia(otro)
    claro, oscuro = max(a, b), min(a, b)
    return (claro + 0.05) / (oscuro + 0.05)


class BarraDePartidoLegibleTests(SimpleTestCase):
    def setUp(self):
        self.css = BARRA.read_text(encoding="utf-8")
        # Los comentarios nombran los tokens culpables para explicar el fallo: se quitan
        # antes de comprobar que ya no PINTAN nada.
        self.reglas = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)

    def _variables(self, selector):
        bloque = re.search(re.escape(selector) + r"\s*\{(.*?)\}", self.reglas, re.S)
        self.assertIsNotNone(bloque, f"falta el bloque {selector}")
        return dict(re.findall(r"(--rail-[a-z-]+)\s*:\s*([^;]+);", bloque.group(1)))

    def test_la_barra_no_mezcla_su_fondo_con_las_letras_del_tema(self):
        """La causa exacta del fallo: fondo propio + color heredado del tema."""
        for token in ("--prod-text", "--prod-muted", "--prod-secondary"):
            self.assertNotIn(
                token,
                self.reglas,
                f"{token} vuelve a pintar la barra: en modo claro se vuelve azul marino",
            )

    def test_el_modo_claro_tiene_sus_propios_colores(self):
        claras = self._variables(':root[data-theme="light"] .matchday-rail')
        self.assertEqual(claras.get("--rail-fondo", "").strip(), "#ffffff")
        self.assertEqual(claras.get("--rail-texto", "").strip(), "#0f172a")

    def test_el_texto_secundario_se_lee_sobre_el_fondo_claro(self):
        """Un negro traslucido no vale: al 68% sobre blanco se queda en 2.8."""
        claras = self._variables(':root[data-theme="light"] .matchday-rail')
        apagado = claras.get("--rail-apagado", "").strip()
        self.assertTrue(apagado.startswith("#"), "tiene que ser un color solido, no un rgba")
        self.assertGreaterEqual(round(_contraste(apagado, "#ffffff"), 2), 4.5)

    def test_el_dorado_de_marca_se_oscurece_en_claro(self):
        claras = self._variables(':root[data-theme="light"] .matchday-rail')
        acento = claras.get("--rail-acento", "").strip()
        self.assertGreaterEqual(
            round(_contraste(acento, "#ffffff"), 2),
            4.5,
            "el #f4b400 de marca sobre blanco se queda en 1.9",
        )

    def test_el_alto_contraste_sigue_siendo_blanco_sobre_negro(self):
        hc = self._variables(':root[data-theme="hc"] .matchday-rail')
        self.assertEqual(hc.get("--rail-fondo", "").strip(), "#000000")
        self.assertEqual(hc.get("--rail-texto", "").strip(), "#ffffff")

    def test_el_tema_oscuro_no_se_toca(self):
        base = self._variables(".matchday-rail")
        self.assertEqual(base.get("--rail-fondo", "").strip(), "rgba(4, 10, 22, 0.96)")
        self.assertEqual(base.get("--rail-texto", "").strip(), "#f5f7fa")
