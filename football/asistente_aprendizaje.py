"""Lo que el asistente NO ha sabido hacer, apuntado para poder enseñárselo.

Por qué esto y no una lista de tareas escrita a mano: enseñarle "todo" es imposible y además
es la forma más cara de equivocarse. Lo que sí se puede es enseñarle **lo que tú le pides de
verdad**, y para saberlo hay que apuntarlo. Cada frase que se le escapa es una línea del plan,
escrita por el uso y no por una suposición mía.

Se guarda en las preferencias del espacio de trabajo (una columna JSON que ya existe), así que
no hace falta migración ni tabla nueva, y sobrevive a los despliegues —a diferencia de un
fichero, que en este servidor se borra en cada uno—.

Se guarda la frase, la fecha y cuántas veces se ha repetido. Nada más: ni quién ni desde dónde.
"""
from __future__ import annotations

import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

CLAVE = "asistente_sin_entender"
MAXIMO = 200
LARGO_MAXIMO = 160


def _normalizar(frase: str) -> str:
    """Agrupa variantes de lo mismo: sobran las mayúsculas y los signos para contar repeticiones."""
    limpio = re.sub(r"\s+", " ", str(frase or "").strip().lower())
    return limpio[:LARGO_MAXIMO]


def apuntar(workspace, frase: str) -> None:
    if not workspace:
        return
    texto = _normalizar(frase)
    if len(texto) < 4:
        return
    try:
        from football.system_guard import _pref_value, _store_pref_value

        filas = _pref_value(workspace, CLAVE, [])
        if not isinstance(filas, list):
            filas = []
        for fila in filas:
            if isinstance(fila, dict) and fila.get("frase") == texto:
                fila["veces"] = int(fila.get("veces") or 1) + 1
                fila["ultima"] = date.today().isoformat()
                break
        else:
            filas.append({"frase": texto, "veces": 1, "ultima": date.today().isoformat()})
        # Las más pedidas primero, y con tope: esto es un cuaderno de notas, no un registro.
        filas.sort(key=lambda f: (int(f.get("veces") or 0), str(f.get("ultima") or "")), reverse=True)
        _store_pref_value(workspace, CLAVE, filas[:MAXIMO])
    except Exception:
        logger.debug("no se pudo apuntar la frase sin entender", exc_info=True)


def leer(workspace, tope: int = 40):
    if not workspace:
        return []
    try:
        from football.system_guard import _pref_value

        filas = _pref_value(workspace, CLAVE, [])
        if not isinstance(filas, list):
            return []
        return [f for f in filas if isinstance(f, dict)][: max(1, int(tope))]
    except Exception:
        return []


def olvidar_todo(workspace) -> None:
    try:
        from football.system_guard import _store_pref_value

        _store_pref_value(workspace, CLAVE, [])
    except Exception:
        pass
