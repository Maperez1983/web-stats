"""Pone las figuras base una al lado de otra, para mirarlas juntas antes de darlas por buenas."""
import os
import sys

from PIL import Image, ImageDraw

REPO = os.environ.get("WEBSTATS_REPO") or "/Volumes/Mac Satecchi/Mac/Web-stats-analysis-entry-clean"
LIB = os.path.join(REPO, "football/static/football/images/coach_roster_avatars/library")

FIGURAS = [
    ("peque_a", "nino_peque_a_hd.png", "6-9"),
    ("peque_b", "nino_peque_b_hd.png", "6-9"),
    ("peque_c", "nino_peque_c_hd.png", "6-9"),
    ("medio_a", "nino_medio_a_hd.png", "10-13"),
    ("medio_b", "nino_medio_b_hd.png", "10-13"),
    ("ado_a", "nino_ado_a_hd.png", "14-15"),
    ("ado_b", "nino_ado_b_hd.png", "14-15"),
    ("adulto", "kit_home_hd.png", "16+"),
]

ALTO = 620
salida = sys.argv[1] if len(sys.argv) > 1 else "/tmp/figuras_por_edad.png"

ims = []
for clave, fichero, tramo in FIGURAS:
    ruta = os.path.join(LIB, fichero)
    if not os.path.exists(ruta):
        continue
    im = Image.open(ruta).convert("RGBA")
    im = im.resize((int(im.size[0] * ALTO / im.size[1]), ALTO))
    ims.append((clave, tramo, im))

if not ims:
    raise SystemExit("No hay ninguna figura generada todavia.")

margen, pie = 18, 34
W = sum(i.size[0] for _, _, i in ims) + margen * (len(ims) + 1)
lienzo = Image.new("RGB", (W, ALTO + pie + margen), (238, 240, 243))
d = ImageDraw.Draw(lienzo)
x = margen
for clave, tramo, im in ims:
    lienzo.paste(im, (x, margen), im)
    d.text((x + 4, ALTO + margen + 6), f"{clave}  ({tramo} anos)", fill=(20, 24, 32))
    x += im.size[0] + margen
lienzo.save(salida)
print("OK", salida)
