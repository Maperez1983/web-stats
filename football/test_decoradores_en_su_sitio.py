"""
Que un decorador no se quede en la función equivocada.

`views.py` tiene decenas de miles de líneas y las funciones auxiliares se van insertando
entre medias. Si una se coloca justo debajo de un `@login_required`, se lleva el decorador
que era de la vista siguiente: la auxiliar recibe comprobaciones que no le tocan (y falla
con "'X' object has no attribute 'user'") y la vista se queda SIN protección.

Ha pasado tres veces en este fichero. Esta prueba lo detecta sola.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


DECORADORES_DE_VISTA = {
    "@login_required",
    "@ensure_csrf_cookie",
    "@require_POST",
    "@require_GET",
    "@csrf_exempt",
    "@authenticated_write",
}


def _funciones_auxiliares_con_decorador_de_vista(ruta):
    lineas = Path(ruta).read_text(encoding="utf-8").split("\n")
    sospechosas = []
    for i, linea in enumerate(lineas):
        # Auxiliar = nombre que empieza por guion bajo y está a nivel de módulo.
        if not re.match(r"^def _\w+\(", linea):
            continue
        decoradores = []
        j = i - 1
        while j >= 0 and lineas[j].strip().startswith("@"):
            decoradores.insert(0, lineas[j].strip().split("(")[0])
            j -= 1
        encontrados = [d for d in decoradores if d in DECORADORES_DE_VISTA]
        if encontrados:
            nombre = linea[4 : linea.index("(")]
            sospechosas.append((nombre, encontrados, i + 1))
    return sospechosas


class DecoradoresEnSuSitioTests(SimpleTestCase):
    def test_ninguna_auxiliar_se_queda_con_el_decorador_de_una_vista(self):
        base = Path(settings.BASE_DIR) / "football"
        problemas = []
        for fichero in ("views.py", "account_views.py", "avatar_data_views.py"):
            ruta = base / fichero
            if ruta.exists():
                for nombre, decoradores, linea in _funciones_auxiliares_con_decorador_de_vista(ruta):
                    problemas.append(f"{fichero}:{linea} {nombre} lleva {', '.join(decoradores)}")

        self.assertEqual(
            problemas,
            [],
            "Hay decoradores de vista sobre funciones auxiliares. Casi siempre significa que la "
            "vista de debajo se ha quedado sin ellos:\n  " + "\n  ".join(problemas),
        )
