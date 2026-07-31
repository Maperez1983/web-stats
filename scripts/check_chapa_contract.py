#!/usr/bin/env python3
"""Candado de la CHAPA del editor 2D.

La chapa (ficha con el escudo del club) se rompio dos veces del mismo modo: nadie
toco el PNG, pero el codigo que compone la ficha le pinto cosas encima o le cambio
el estilo por detras. Este script congela ese comportamiento.

Se ejecuta en `build.sh` ANTES de collectstatic: si algo de esto se rompe, el
despliegue falla y Render mantiene la version anterior en produccion. Tambien lo
corre `football/test_chapa_contract.py` con `manage.py test`.

QUITAR O RELAJAR ESTAS COMPROBACIONES REQUIERE PETICION EXPRESA DEL PROPIETARIO.
No las "arregles" para que pase el build: si fallan, el fallo esta en el editor.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAD = ROOT / "football" / "static" / "football" / "js" / "sessions_tactical_pad.js"
CHAPA_DIR = ROOT / "football" / "static" / "football" / "images" / "chapa"

# Las 8 equipaciones del catalogo (CHAPA_KEY en el editor).
CHAPA_FILES = [
    "chapa_local.png",
    "chapa_away.png",
    "chapa_turquesa.png",
    "chapa_blanca.png",
    "chapa_chandal.png",
    "chapa_gk_azul.png",
    "chapa_gk_negra.png",
    "chapa_gk_magenta.png",
]


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def _strip_comments(src: str) -> str:
    """Quita comentarios para que las comprobaciones miren CODIGO, no prosa.

    Sin esto, un comentario que menciona el patron prohibido (p.ej. explicando por que
    se quito) hace saltar el candado. Basta con ser conservador: no intentamos parsear
    JS, solo vaciamos // ... y /* ... */ respetando cadenas simples.
    """
    out = []
    i, n = 0, len(src)
    quote = None
    while i < n:
        ch = src[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def check(problems: list[str]) -> None:
    if not PAD.exists():
        _fail(problems, f"no encuentro {PAD.relative_to(ROOT)}")
        return
    raw = PAD.read_text(encoding="utf-8")
    src = _strip_comments(raw)

    # 1) Los 8 PNG existen y no estan vacios.
    for name in CHAPA_FILES:
        path = CHAPA_DIR / name
        if not path.exists():
            _fail(problems, f"falta la chapa {name} en {CHAPA_DIR.relative_to(ROOT)}")
        elif path.stat().st_size < 10_000:
            _fail(problems, f"la chapa {name} pesa {path.stat().st_size} B: parece truncada o vacia")

    # 2) applyTokenColor NO puede recolorear una ficha dibujada con la imagen de chapa.
    #    Sin este guard, el color del kit acaba pintando un aro decorativo que va ENCIMA
    #    del PNG y tapa el escudo (bug de 2026-07-31).
    #    No basta con que exista la variable: exigimos la salida temprana real
    #    `if (usesChapaImage) { ... return; }`.
    guard = re.search(r"if\s*\(\s*usesChapaImage\s*\)\s*\{[^}]{0,200}\breturn\b", src)
    if not guard:
        _fail(
            problems,
            "applyTokenColor ha perdido la salida temprana `if (usesChapaImage) { ... return; }`: "
            "volvera a pintar un disco liso encima del escudo de la chapa",
        )
    #    Y que se detecte mirando una IMAGEN con rol token_base (la chapa dibujada como PNG).
    if not re.search(r"child\.type\s*[!=]==\s*'image'", src) or "token_base" not in src:
        _fail(
            problems,
            "el guard ya no detecta la chapa-imagen (child.type === 'image' con role token_base)",
        )

    # 3) Prohibido volver a elegir el circulo a recolorear POR POSICION. Esa heuristica
    #    (`circles[1]`) es exactamente lo que dejo de apuntar al disco base cuando cambio
    #    el orden de capas. Debe buscarse por ROL.
    if re.search(r"circles\s*\[\s*1\s*\]", src):
        _fail(
            problems,
            "ha vuelto la heuristica `circles[1]` (elegir capa por posicion) en el "
            "recoloreado de fichas: usa el rol (token_fill / token_base)",
        )
    if "token_fill" not in src or "token_base" not in src:
        _fail(problems, "faltan los roles token_fill / token_base que identifican el disco base")

    # 4) La CHAPA no puede tratarse como 'sin estilo elegido'. Si vuelve el
    #    `|| tokenGlobalStyle === 'disk'`, elegir Chapa deja de sobrevivir a una recarga.
    if re.search(r"tokenGlobalStyleStored\s*\|\|\s*tokenGlobalStyle\s*===\s*'disk'", src):
        _fail(
            problems,
            "applyKit2dDefaultTokenStyle vuelve a convertir CHAPA en CAMISETA: quita "
            "el `|| tokenGlobalStyle === 'disk'` de su condicion",
        )

    # 5) Cambiar el estilo global debe repintar las fichas YA colocadas, no solo el banco.
    if "applyGlobalTokenStyleToCanvas" not in src:
        _fail(
            problems,
            "falta applyGlobalTokenStyleToCanvas: el selector Chapa/Camiseta/Foto/Avatar "
            "volveria a no aplicar a las fichas ya colocadas",
        )
    else:
        # Cuenta INVOCACIONES (la definicion es `const applyGlobalTokenStyleToCanvas = (...`,
        # con `= (` en medio, asi que no cuela como llamada).
        calls = len(re.findall(r"(?<!\w)applyGlobalTokenStyleToCanvas\(", src))
        if calls < 2:
            _fail(
                problems,
                f"applyGlobalTokenStyleToCanvas se invoca {calls} vez/veces; deben llamarla los "
                "DOS manejadores del selector (data-global-token-style y data-bank-style)",
            )


def main() -> int:
    problems: list[str] = []
    check(problems)
    if problems:
        sys.stderr.write("\nCONTRATO DE LA CHAPA ROTO:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        sys.stderr.write(
            "\nEste candado es intencionado. La chapa con escudo es el formato aprobado por el\n"
            "propietario; no lo cambies para que pase el build. Ver scripts/check_chapa_contract.py\n\n"
        )
        return 1
    print("contrato de la chapa: OK (8 equipaciones + 4 invariantes del editor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
