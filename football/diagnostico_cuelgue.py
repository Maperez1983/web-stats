"""Vigilante de peticiones que se cuelgan: dice EN QUE LINEA se quedan paradas.

Por que existe: `/api/system/guard-chat/` se cuelga >35 s en produccion y en local no se
reproduce (alli no hay `django_error.log`, ni conectores configurados, ni URL publica). Se
arreglaron cuatro cosas a ojo y ninguna era la causa. Esto deja de adivinar: si la peticion
pasa de N segundos, se vuelca la pila del hilo que la esta atendiendo.

Donde escribe y por que a un FICHERO y no a la cache: la cache por defecto es LocMemCache,
que NO se comparte entre los workers de gunicorn, asi que quien luego venga a leer el volcado
puede caer en otro worker y no ver nada. El disco del contenedor si lo comparten.

Se activa solo con PERF_SERVER_TIMING, la misma variable del resto del diagnostico.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

FICHERO = "diagnostico_cuelgues.log"
MAX_BYTES = 512 * 1024


def activado() -> bool:
    return str(os.getenv("PERF_SERVER_TIMING", "0") or "").strip().lower() in {"1", "true", "yes", "on"}


def _ruta() -> Path:
    return Path(getattr(settings, "BASE_DIR", ".")) / FICHERO


def _apuntar(texto: str) -> None:
    try:
        ruta = _ruta()
        # Truncado sencillo: si crece, se empieza de cero. Es diagnostico, no un registro serio,
        # y justamente uno de los fallos que encontramos fue un log que crecia sin control.
        if ruta.exists() and ruta.stat().st_size > MAX_BYTES:
            ruta.unlink()
        with ruta.open("a", encoding="utf-8") as fichero:
            fichero.write(texto)
    except Exception:
        pass


def _volcar(etiqueta: str, hilo_id: int, empezado: float) -> None:
    try:
        marco = sys._current_frames().get(hilo_id)
        if marco is None:
            return
        pila = traceback.format_stack(marco)
        # Solo los marcos del proyecto: la pila entera son 60 lineas de Django y wsgi.
        raiz = str(getattr(settings, "BASE_DIR", ""))
        nuestros = [ln for ln in pila if f"{raiz}/football" in ln or f"{raiz}/webstats" in ln]
        cuerpo = "".join(nuestros[-12:] or pila[-8:])
        _apuntar(
            f"\n=== {etiqueta} · lleva {time.perf_counter() - empezado:.1f} s parada "
            f"· {time.strftime('%H:%M:%S')}\n{cuerpo}"
        )
    except Exception:
        pass


@contextmanager
def vigilar(etiqueta: str, *, avisos=(8, 20, 40)):
    """Vuelca la pila del hilo actual a los N segundos, si la peticion sigue viva."""
    if not activado():
        yield
        return
    hilo_id = threading.get_ident()
    empezado = time.perf_counter()
    temporizadores = []
    for segundos in avisos:
        t = threading.Timer(segundos, _volcar, args=(etiqueta, hilo_id, empezado))
        t.daemon = True
        t.start()
        temporizadores.append(t)
    try:
        yield
    finally:
        for t in temporizadores:
            try:
                t.cancel()
            except Exception:
                pass
        tardanza = time.perf_counter() - empezado
        if tardanza >= min(avisos):
            _apuntar(f"--- {etiqueta} TERMINO en {tardanza:.1f} s\n")


def leer(max_bytes: int = 60_000) -> str:
    """La cola del fichero de volcados."""
    ruta = _ruta()
    if not ruta.exists():
        return ""
    try:
        with ruta.open("rb") as fichero:
            fichero.seek(0, os.SEEK_END)
            tam = fichero.tell()
            fichero.seek(max(0, tam - max_bytes))
            return fichero.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def limpiar() -> None:
    try:
        _ruta().unlink()
    except Exception:
        pass
