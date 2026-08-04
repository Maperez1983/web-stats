"""
Cada dato de la ficha, en una sola pestaña.

"Datos personales" acumulaba cinco cosas distintas: la persona, lo deportivo, el cuerpo, lo
administrativo y dos operaciones serias (mover de equipo, traspaso). Altura y peso estaban
ADEMÁS en Salud, y dorsal y posición en la cabecera: el mismo dato en dos sitios acaba
descuadrado y nadie sabe cuál vale.
"""

import re

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


FICHA = Path(settings.BASE_DIR) / "football" / "templates" / "football" / "player_detail.html"


def _panel_de_cada(texto, clave):
    """Paneles (`data-pane`) en los que aparece una etiqueta."""
    contenido = FICHA.read_text(encoding="utf-8")
    paneles = []
    for encontrado in re.finditer(re.escape(clave), contenido):
        previos = list(re.finditer(r'data-pane="([a-z]+)"', contenido[: encontrado.start()]))
        paneles.append(previos[-1].group(1) if previos else "cabecera")
    return sorted(set(paneles))


class CadaDatoEnUnSitioTests(SimpleTestCase):
    def test_datos_personales_ya_no_lleva_lo_administrativo(self):
        contenido = FICHA.read_text(encoding="utf-8")
        personal = contenido[contenido.index('data-pane="personal"') : contenido.index('data-pane="agenda"')]

        for fuera in ["Cláusula", "Agente", "Club de origen", "Ficha federativa"]:
            self.assertNotIn(fuera, personal, f"{fuera} sigue en Datos personales")

    def test_datos_personales_ya_no_lleva_el_traspaso(self):
        contenido = FICHA.read_text(encoding="utf-8")
        personal = contenido[contenido.index('data-pane="personal"') : contenido.index('data-pane="agenda"')]

        self.assertNotIn("Estado en el club", personal, "El traspaso sigue entre los datos de la persona")

    def test_dorsal_y_posicion_no_se_repiten_en_datos_personales(self):
        contenido = FICHA.read_text(encoding="utf-8")
        personal = contenido[contenido.index('data-pane="personal"') : contenido.index('data-pane="agenda"')]

        self.assertNotIn(">Dorsal<", personal, "El dorsal ya está en la cabecera")

    def test_la_persona_y_su_contacto_siguen_en_su_sitio(self):
        contenido = FICHA.read_text(encoding="utf-8")
        personal = contenido[contenido.index('data-pane="personal"') : contenido.index('data-pane="agenda"')]

        for dentro in ["Teléfono", "Email", "De quién es", "Nombre completo", "Nacimiento"]:
            self.assertIn(dentro, personal, f"{dentro} debería seguir en Datos personales")

    def test_altura_y_peso_solo_en_salud(self):
        self.assertEqual(_panel_de_cada(FICHA, "Altura"), ["salud"])
        self.assertEqual(_panel_de_cada(FICHA, "Peso"), ["salud"])
