"""Fabrica el RECORTE de ficha de campo a partir de la foto que ha subido cada jugador.

Hasta ahora los recortes se hacían a mano y se commiteaban con el nombre `<slug>-n<dorsal>-cut.png`;
había 22, todos del senior. Este script hace lo mismo en lote: baja la foto, le quita el fondo y
la deja recortada al contorno.

Se guardan como `player-<id>.png`, y eso NO es un detalle:
  - es el primer nombre que busca `resolve_player_photo_static_path`, y lo busca en la carpeta
    global para TODOS los equipos; los nombres con slug sólo se miran en la carpeta del equipo
    (y en la global sólo para el senior), así que un cadete nunca encontraría el suyo;
  - no lleva el dorsal, así que cambiarle el número a un jugador no le deja sin recorte;
  - no lleva el nombre, así que corregirle una tilde tampoco.

NO pisa los recortes hechos a mano: `player-<id>.png` se busca ANTES, así que generarlo para
alguien que ya tiene el suyo lo taparía, y el hecho a mano está mejor encuadrado.

    python recortes_desde_fotos.py            # baja, recorta y monta la hoja para mirarlo
    python recortes_desde_fotos.py --instalar # además los copia al repo
"""
import io
import json
import os
import sys

import boto3
import psycopg2
import psycopg2.extras
from PIL import Image

REPO = "/Volumes/Mac Satecchi/Mac/Web-stats-analysis-entry-clean"
DESTINO_REPO = os.path.join(REPO, "static/football/images/players")
ORIGEN = "recortes/origen"
SALIDA = "recortes/salida"
ALTO_MAX = 768          # el mismo que tienen los hechos a mano

env = {}
for l in open(os.path.join(REPO, ".env.avatars")):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

os.makedirs(ORIGEN, exist_ok=True)
os.makedirs(SALIDA, exist_ok=True)
instalar = "--instalar" in sys.argv

# 1) Quién tiene foto subida
con = psycopg2.connect(env["DATABASE_URL"])
con.set_session(readonly=True, autocommit=True)
cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)
EQUIPOS_DEL_CLUB = [1, 29, 67, 68]      # Benagalbón: senior, prebenjamín, benjamín B, cadete
cur.execute("""
    SELECT p.id, p.name, p.number, t.name AS equipo, t.category, t.is_primary
    FROM football_player p JOIN football_team t ON t.id = p.team_id
    WHERE p.is_active = true AND p.photo_updated_at IS NOT NULL
      -- SOLO los equipos del club. La carpeta `static/football/images/players/` es CODIGO
      -- compartido por todo el despliegue, no media por workspace: meter ahi las fotos de otro
      -- club -hay mas de uno en la base- seria meter a un cliente en el repositorio.
      AND t.id = ANY(%(equipos)s)
    ORDER BY t.name, p.number NULLS LAST, p.name
""", {"equipos": EQUIPOS_DEL_CLUB})
todos = [dict(r) for r in cur.fetchall()]

# 2) Quién YA tiene recorte hecho a mano (no se le toca)
import re, unicodedata

def slugify(v):
    """El mismo slug que usa Django para buscar el fichero."""
    v = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode()
    v = re.sub(r"[^\w\s-]", "", v).strip().lower()
    return re.sub(r"[-\s]+", "-", v)

ya_hechos = set(os.listdir(DESTINO_REPO)) if os.path.isdir(DESTINO_REPO) else set()


def tiene_recorte(f):
    slug = slugify(f["name"] or "")
    num = f["number"] if f["number"] is not None else ""
    posibles = {f"player-{f['id']}.png"}
    if slug and num != "":
        posibles |= {f"{slug}-n{num}-cut.png", f"{slug}-n{num}-final.png", f"{slug}-n{num}.png"}
    if slug:
        posibles |= {f"{slug}-final.png", f"{slug}.png"}
    return bool(posibles & ya_hechos)


pendientes = [f for f in todos if not tiene_recorte(f)]
print(f"con foto subida: {len(todos)}   ya tienen recorte: {len(todos) - len(pendientes)}   "
      f"a fabricar: {len(pendientes)}")
from collections import Counter  # noqa: E402
for (eq,), n in sorted(Counter((f["equipo"],) for f in pendientes).items()):
    print(f"   {eq}: {n}")

if not pendientes:
    print("\nno hay nada que hacer")
    sys.exit(0)

# 3) Bajar las fotos
s3 = boto3.client("s3", aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
                  aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"], region_name="eu-west-3")
BUCKET = env["AWS_STORAGE_BUCKET_NAME"]
EXT = (".png", ".jpg", ".jpeg", ".webp")
bajadas = []
for f in pendientes:
    destino = os.path.join(ORIGEN, f"player-{f['id']}.bin")
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        bajadas.append(f)
        continue
    for ext in EXT:
        try:
            s3.download_file(BUCKET, f"media/player-photos/player-{f['id']}{ext}", destino)
            bajadas.append(f)
            break
        except Exception:
            continue
print(f"\nfotos bajadas: {len(bajadas)} de {len(pendientes)}")

# 4) Quitar el fondo y recortar al contorno
#
# Se llama al modelo u2net DIRECTAMENTE con onnxruntime en vez de usar `rembg`: rembg importa
# `pymatting` sin condiciones y eso arrastra numba y llvmlite, que en este Python no cargan. El
# modelo es el mismo (`~/.u2net/u2net.onnx`, el que baja rembg); lo unico que se pierde es el
# alpha matting opcional, que aqui no se usa.
import numpy as np  # noqa: E402
import onnxruntime  # noqa: E402

_MODELO = os.path.expanduser("~/.u2net/u2net.onnx")
_sesion = onnxruntime.InferenceSession(_MODELO, providers=["CPUExecutionProvider"])
_MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_DESV = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def remove(im):
    """La foto con el fondo transparente. Mismo preproceso que rembg para u2net."""
    original = im.convert("RGBA")
    chico = np.asarray(original.convert("RGB").resize((320, 320), Image.LANCZOS)).astype(np.float32) / 255.0
    chico = (chico - _MEDIA) / _DESV
    entrada = np.expand_dims(chico.transpose(2, 0, 1), 0).astype(np.float32)
    salida = _sesion.run(None, {_sesion.get_inputs()[0].name: entrada})[0][0, 0]
    salida = (salida - salida.min()) / max(salida.max() - salida.min(), 1e-8)
    mascara = Image.fromarray((salida * 255).astype("uint8"), "L").resize(original.size, Image.LANCZOS)
    fuera = original.copy()
    fuera.putalpha(mascara)
    return fuera

# Dos guardas, porque un recorte malo en la pizarra es peor que la figura generica:
#  - LADO MINIMO: las cinco fotos del cadete resultaron ser miniaturas de 150x180. De ahi no sale
#    un recorte, sale una mancha; y ampliarla la empeora.
#  - BORDE BORROSO: si el modelo no encuentra un sujeto limpio deja medio contorno a medias. Un
#    recorte bueno tiene menos del 15% de pixeles ni opacos ni transparentes; los malos pasaban
#    del 27% y llegaban al 57%.
LADO_MINIMO = 400
BORDE_MAXIMO = 20.0

hechos, rechazados = [], []
for f in bajadas:
    origen = os.path.join(ORIGEN, f"player-{f['id']}.bin")
    try:
        with Image.open(origen) as im:
            if max(im.size) < LADO_MINIMO:
                rechazados.append({**f, "motivo": f"la foto es de {im.size[0]}x{im.size[1]}: es una miniatura"})
                continue
            recorte = remove(im.convert("RGBA"))
        import numpy as _np
        _a = _np.asarray(recorte)[..., 3]
        _borde = float(((_a > 20) & (_a < 235)).sum()) / max(int((_a > 20).sum()), 1) * 100
        if _borde > BORDE_MAXIMO:
            rechazados.append({**f, "motivo": f"el recorte sale con {_borde:.0f}% de borde borroso"})
            continue
        caja = recorte.split()[3].getbbox()
        if caja:
            recorte = recorte.crop(caja)
        if recorte.height > ALTO_MAX:
            ancho = int(ALTO_MAX * recorte.width / recorte.height)
            recorte = recorte.resize((ancho, ALTO_MAX), Image.LANCZOS)
        ruta = os.path.join(SALIDA, f"player-{f['id']}.png")
        recorte.save(ruta, optimize=True)
        hechos.append({**f, "fichero": ruta})
    except Exception as e:
        print(f"  fallo {f['id']} {f['name']}: {e}")
print(f"recortes hechos: {len(hechos)}")
if rechazados:
    print(f"\nRECHAZADOS ({len(rechazados)}) - necesitan una foto mejor:")
    for r in rechazados:
        print(f"   {r['name']} ({r['equipo']}): {r['motivo']}")
json.dump(rechazados, open("recortes/rechazados.json", "w"), ensure_ascii=False, indent=1, default=str)
json.dump(hechos, open("recortes/hechos.json", "w"), ensure_ascii=False, indent=1, default=str)

# 5) Hoja para mirarlos
if hechos:
    COL, CW, CH = 8, 150, 200
    filas = (len(hechos) + COL - 1) // COL
    lienzo = Image.new("RGB", (COL * CW, filas * CH), (30, 60, 40))
    for n, h in enumerate(hechos):
        im = Image.open(h["fichero"]).convert("RGBA")
        im.thumbnail((CW - 14, CH - 14))
        lienzo.paste(im, ((n % COL) * CW + (CW - im.width) // 2,
                          (n // COL) * CH + (CH - im.height) // 2), im)
    lienzo.save("out/recortes_nuevos.png")
    print("hoja: out/recortes_nuevos.png")

if not instalar:
    print("\n(simulación: no se ha copiado nada al repo. Con --instalar se aplica)")
    sys.exit(0)

import shutil  # noqa: E402
for h in hechos:
    shutil.copy(h["fichero"], os.path.join(DESTINO_REPO, f"player-{h['id']}.png"))
print(f"\n{len(hechos)} recortes copiados a static/football/images/players/")
