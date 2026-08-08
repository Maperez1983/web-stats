"""La ficha de tarea tiene que leerse en modo claro.

Forzaba el fondo OSCURO tambien en claro (`background: linear-gradient(...) !important`),
pero los paneles de dentro si se volvian blancos con el tema: fondo negro, tarjeta blanca y
letra blanca encima. Medido en produccion: 16 elementos por debajo de 3 de contraste, y las
pestanas ("Presentacion", "Pizarra", "1 · Que se hace") en 1.1, o sea invisibles.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

FICHA = (
    Path(__file__).resolve().parent / "templates" / "football" / "session_task_detail.html"
)

SELECTOR_CLARO = ':root[data-theme="light"] body.prod-commercial.session-task-detail-page'


def _luminancia(hex_color):
    hex_color = hex_color.lstrip("#")
    canales = [int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lineal = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _contraste(uno, otro):
    a, b = _luminancia(uno), _luminancia(otro)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


class FichaDeTareaEnModoClaroTests(SimpleTestCase):
    def setUp(self):
        self.fuente = FICHA.read_text(encoding="utf-8")
        bloque = re.search(re.escape(SELECTOR_CLARO) + r"\s*\{(.*?)\}", self.fuente, re.S)
        self.assertIsNotNone(bloque, "la ficha no declara sus colores para el modo claro")
        self.claro = bloque.group(1)

    def _variable(self, nombre):
        encontrado = re.search(rf"{re.escape(nombre)}\s*:\s*([^;]+);", self.claro)
        self.assertIsNotNone(encontrado, f"falta {nombre} en el bloque de modo claro")
        return encontrado.group(1).strip()

    def test_el_modo_claro_ya_no_impone_el_fondo_oscuro(self):
        """La regla que lo rompia todo: un degradado casi negro forzado con !important."""
        fondo = re.search(r"background\s*:\s*([^;]+);", self.claro)
        self.assertIsNotNone(fondo)
        self.assertNotIn("#020916", fondo.group(1))
        self.assertNotIn("#081b35", fondo.group(1))

    def test_la_letra_se_oscurece_en_claro(self):
        tinta = self._variable("--ink")
        self.assertTrue(tinta.startswith("#"), "tiene que ser un color solido")
        self.assertGreaterEqual(round(_contraste(tinta, "#ffffff"), 2), 4.5)

    def test_las_pastillas_de_pestana_no_fijan_un_blanco_translucido(self):
        """`background: rgba(255,255,255,.06)` sobre blanco no pinta nada, y la letra iba en
        `--ink`, que era casi blanco: pastillas invisibles."""
        for clase in (".task-detail-tab", ".task-edit-tab", ".task-settings-tab"):
            bloque = re.search(re.escape(clase) + r"\s*\{(.*?)\}", self.fuente, re.S)
            self.assertIsNotNone(bloque, f"no encuentro {clase}")
            self.assertNotIn(
                "rgba(255, 255, 255, 0.0",
                bloque.group(1),
                f"{clase} vuelve a fijar un fondo blanco translucido en vez de usar el tema",
            )

    def test_la_caja_de_seccion_cambia_con_el_tema(self):
        """Iba en azul marino translucido: sobre blanco salia un slab gris."""
        self.assertIn("--ficha-seccion", self.claro)
        bloque = re.search(r"\.editor-section\s*\{(.*?)\}", self.fuente, re.S)
        self.assertIsNotNone(bloque)
        self.assertIn("var(--ficha-seccion)", bloque.group(1))

    def test_el_alto_contraste_sigue_siendo_negro(self):
        bloque = re.search(
            r':root\[data-theme="hc"\] body\.prod-commercial\.session-task-detail-page\s*\{(.*?)\}',
            self.fuente,
            re.S,
        )
        self.assertIsNotNone(bloque)
        self.assertIn("#000000", bloque.group(1))

    def test_el_tema_oscuro_no_se_toca(self):
        bloque = re.search(r"body\.session-task-detail-page\s*\{(.*?)\}", self.fuente, re.S)
        self.assertIsNotNone(bloque)
        self.assertIn("--ink: #f3f4f6", bloque.group(1))
