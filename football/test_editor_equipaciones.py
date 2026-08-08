"""En el editor de tareas se tiene que poder elegir CUALQUIER equipación, sin limitación.

Comprobado a mano en producción antes de tocar nada: el motor sabía pintar las ocho
equipaciones (se colocaron las ocho por script y salieron bien), pero por la interfaz no
había forma de llegar a ellas.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent
MOTOR = RAIZ / "static" / "football" / "js" / "sessions_tactical_pad.js"
BARRA = RAIZ / "templates" / "football" / "includes" / "task_builder" / "editor_chrome.html"
LIENZO = RAIZ / "templates" / "football" / "includes" / "task_builder" / "canvas_viewport.html"


class ElegirEquipacionTests(SimpleTestCase):
    def setUp(self):
        self.motor = MOTOR.read_text(encoding="utf-8")
        self.barra = BARRA.read_text(encoding="utf-8")
        self.lienzo = LIENZO.read_text(encoding="utf-8")

    def test_los_selectores_ganan_al_tema_y_se_ven(self):
        """commercial.css pinta `button{background:...!important}` y dejaba los OCHO
        selectores en blanco: era imposible ver cuál estabas eligiendo."""
        self.assertIn("--sw", self.barra)
        self.assertRegex(self.barra, r"background:\s*var\(--sw\)\s*!important")
        # Y ADEMAS en el propio elemento: la regla de hoja perdia de forma intermitente
        # segun cuando terminaba de montarse la barra. Un inline con !important esta por
        # encima de cualquier hoja, gane quien gane la carrera.
        muestras = re.findall(r'class="edc-swatch[^"]*"[^>]*style="([^"]+)"', self.barra)
        self.assertEqual(len(muestras), 9, "tienen que ser las 9 equipaciones")
        for estilo in muestras:
            self.assertRegex(estilo, r"background:[^;]+!important")

    def test_y_tambien_ganan_en_MODO_CLARO(self):
        """Con las dos reglas en !important manda la más específica, y en claro
        commercial.css sube a `:root[data-theme="light"] body.prod-commercial :where(button…)`.
        Un `.edc-swatch[...]` a secas arreglaba el oscuro y dejaba el claro igual de blanco:
        es el tema que él usa, así que el arreglo no se veía."""
        self.assertIn(
            ':root[data-theme="light"] body.prod-commercial .edc-swatch[data-kit]', self.barra
        )
        self.assertIn(
            ':root[data-theme="light"] body.prod-commercial .edc-swatch[data-gk]', self.barra
        )

    def test_la_equipacion_de_entreno_esta_en_la_barra(self):
        """Es la que más se ve: casi todo lo que se dibuja en la pizarra son sesiones."""
        self.assertIn('data-kit="entreno"', self.barra)

    def test_la_barra_ofrece_las_seis_de_campo_y_las_tres_de_portero(self):
        campo = set(re.findall(r'data-kit="([a-z_]+)"', self.barra))
        portero = set(re.findall(r'data-gk="([a-z_]+)"', self.barra))
        self.assertEqual(
            campo, {"titular", "visitante", "turquesa", "blanca", "entreno", "chandal"}
        )
        self.assertEqual(portero, {"gk_azul", "gk_negra", "gk_magenta"})

    def test_el_inspector_tambien_llega_a_entreno_y_chandal(self):
        huecos = set(re.findall(r'data-token-kit-slot="([a-z0-9]+)"', self.lienzo))
        self.assertEqual(huecos, {"home", "away", "third", "entreno", "chandal", "gk", "gk2", "gk3"})

    def test_el_rol_ya_no_reescribe_la_eleccion(self):
        """Era un CANDADO: el portero no podía salir con la de entreno aunque el rondo lo
        haga con el equipo, y un jugador de campo no podía ponerse de portero."""
        self.assertNotIn("if (isGk && kit.indexOf('gk_') !== 0) kit = 'gk_azul';", self.motor)
        self.assertNotIn("if (!isGk && kit.indexOf('gk_') === 0) kit = 'titular';", self.motor)

    def test_pero_sigue_habiendo_defecto_por_rol(self):
        """Quitar el candado no puede significar que un portero sin elección salga de campo."""
        self.assertIn("if (!kit) kit = isGk ? 'gk_azul' : 'titular';", self.motor)

    def test_la_eleccion_viaja_como_kit_slot(self):
        """El factory mira `kit_slot`; la elección llegaba sólo como `kit`, que es otra cosa,
        así que elegir equipación no cambiaba la camiseta."""
        self.assertIn("SLOT_POR_KIT", self.motor)
        bloque = re.search(r"const SLOT_POR_KIT = \{(.*?)\};", self.motor, re.S)
        self.assertIsNotNone(bloque)
        for kit, hueco in (
            ("titular", "home"),
            ("visitante", "away"),
            ("entreno", "entreno"),
            ("chandal", "chandal"),
            ("gk_azul", "gk"),
            ("gk_negra", "gk2"),
            ("gk_magenta", "gk3"),
        ):
            self.assertRegex(bloque.group(1), rf"{kit}\s*:\s*'{hueco}'")
        self.assertRegex(self.motor, r"kit_slot:\s*SLOT_POR_KIT\[kit\]")

    def test_la_figura_de_entreno_tiene_su_hueco(self):
        bloque = re.search(r"const FIG_KIND = \{(.*?)\};", self.motor, re.S)
        self.assertIsNotNone(bloque)
        self.assertIn("entreno:'kit_entreno'", bloque.group(1).replace(" ", ""))
