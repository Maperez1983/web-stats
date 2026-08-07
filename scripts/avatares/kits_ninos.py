"""
Fabrica las EQUIPACIONES que le faltaban a las figuras de niño.

Las nueve figuras de niño (`nino_bebe/peque/medio/ado_*_hd.png`) sólo existían en la titular,
mientras que el adulto tenía las cuatro. Por eso, al elegir "visitante" en la pizarra de un
cadete, sólo cambiaba el portero: a los de campo no había con qué cambiarlos.

No se generan de cero con Flux -eso daría otro niño, no el mismo con otra camiseta-: se recolorean
con `uniformar_rayas`, que es la misma función que ya unificó el verde del club en todas ellas.
Reconoce la camiseta porque es lo único que lleva blanco, y el pantalón y las medias porque están
por debajo; los pliegues se conservan escalando la luminancia, así que no queda de cartón.

    python kits_ninos.py                 # las nueve figuras, las tres equipaciones que faltan
    python kits_ninos.py ado_a peque_b   # sólo esas
    python kits_ninos.py --montaje       # además, una hoja para mirarlas juntas

Se ejecuta en el Mac (necesita insightface para encontrar la cara). Escribe en
`football/static/football/images/coach_roster_avatars/library/`.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finish_ninos import cara_de, uniformar_rayas  # noqa: E402

REPO = os.environ.get("WEBSTATS_REPO") or "/Volumes/Mac Satecchi/Mac/Web-stats-analysis-entry-clean"
LIB = os.path.join(REPO, "football/static/football/images/coach_roster_avatars/library")

# Las claves de figura del catálogo `FIGURAS` (generate_player_avatars.py). El adulto no está:
# ya tiene sus cuatro equipaciones dibujadas de verdad.
FIGURAS_NINO = (
    "bebe_a", "bebe_b",
    "peque_a", "peque_b", "peque_c",
    "medio_a", "medio_b",
    "ado_a", "ado_b",
)

# Los colores salen MEDIDOS de las equipaciones de adulto (`kit_away_hd.png`, `kit_turquoise_hd`,
# `kit_white_hd`), no inventados: si no, el cadete y el senior saldrían con dos amarillos
# distintos, que es exactamente lo que se arregló en su día con el verde.
#
# `rango` es cuánto se deja bajar el color con la sombra. La titular lleva rayas blancas, que
# admiten muy poco juego (0,88-1,04) o salen grises; una equipación LISA y oscura admite mucho
# más, y una lisa y clara vuelve a necesitar mano corta.
KITS = {
    "away": {
        "etiqueta": "Visitante",
        "camiseta": (214, 189, 7),
        "pantalon": (214, 189, 7),
        "rango": (0.62, 1.30),
    },
    "turquoise": {
        "etiqueta": "Entreno turquesa",
        "camiseta": (20, 177, 192),
        "pantalon": (7, 43, 71),
        "rango": (0.62, 1.30),
    },
    "white": {
        "etiqueta": "Entreno blanca",
        "camiseta": (196, 205, 216),
        "pantalon": (55, 55, 55),
        "rango": (0.86, 1.08),
    },
}


# Ancho al que se guardan las variantes. La titular se queda a 651 px porque es el MÁSTER del
# generador de avatares; estas no: sólo se usan como figura de pizarra, y ahí la más grande se ve
# a unos 96 px de CSS (192 en pantalla retina) y en el PDF se reduce a 150x180. A 400 px hay
# margen de sobra y las 27 pesan 5,4 MB en vez de 14. Reducir la PALETA en vez del tamaño se
# probó y no vale: posteriza la cara, que es justo lo que se quiere conservar.
ANCHO = 400


def destino_de(clave, kit):
    """`nino_ado_a_hd.png` + away -> `nino_ado_a_away_hd.png`. El sufijo va ANTES del `_hd` para
    que la figura y sus variantes queden juntas al listar la carpeta."""
    return os.path.join(LIB, f"nino_{clave}_{kit}_hd.png")


def fabrica(clave, kits=None):
    origen = os.path.join(LIB, f"nino_{clave}_hd.png")
    if not os.path.exists(origen):
        print(f"  {clave}: NO existe {os.path.basename(origen)}")
        return []
    figura = Image.open(origen).convert("RGBA")
    cara = cara_de(figura)
    if cara is None:
        print(f"  {clave}: no se le encuentra la cara; sin cara no se puede excluir la piel")
        return []
    hechas = []
    for kit, datos in KITS.items():
        if kits and kit not in kits:
            continue
        salida = uniformar_rayas(
            figura,
            cara,
            verde=datos["camiseta"],
            blanco=datos["camiseta"],      # camiseta LISA: las dos bandas del mismo color
            pantalon=datos["pantalon"],
            rango_verde=datos["rango"],
            rango_blanco=datos["rango"],
            # Una equipacion lisa no perdona un verde superviviente: se baja la proteccion de
            # "esto es casi negro, sera un logo" para que entren tambien los pliegues hondos.
            umbral_oscuro=45,
        )
        salida = salida.resize((ANCHO, int(ANCHO * salida.height / salida.width)), Image.LANCZOS)
        ruta = destino_de(clave, kit)
        salida.save(ruta, optimize=True)
        hechas.append(ruta)
        print(f"  {clave} · {datos['etiqueta']:18} -> {os.path.basename(ruta)}")
    return hechas


def montaje(claves):
    """Una hoja con cada figura y sus cuatro equipaciones, para mirarlas de una vez."""
    CW, CH = 150, 330
    columnas = ["", "away", "turquoise", "white"]
    lienzo = Image.new("RGB", (CW * len(columnas), CH * len(claves)), (24, 58, 34))
    for fila, clave in enumerate(claves):
        for col, kit in enumerate(columnas):
            ruta = os.path.join(LIB, f"nino_{clave}_hd.png") if not kit else destino_de(clave, kit)
            if not os.path.exists(ruta):
                continue
            im = Image.open(ruta).convert("RGBA")
            im.thumbnail((CW - 16, CH - 16))
            lienzo.paste(im, (col * CW + (CW - im.width) // 2, fila * CH + (CH - im.height) // 2), im)
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "montaje_kits_ninos.png")
    lienzo.save(ruta)
    print(f"\nmontaje: {ruta}  ({lienzo.size[0]}x{lienzo.size[1]})")
    return ruta


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    claves = args or list(FIGURAS_NINO)
    print(f"Fabricando equipaciones para {len(claves)} figuras:")
    for clave in claves:
        fabrica(clave)
    if "--montaje" in sys.argv:
        montaje(claves)
