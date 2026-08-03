#!/bin/bash
# Figuras base por edad para los avatares.
#
# La unica figura que habia (kit_home_hd.png) es un cuerpo de ADULTO, y este club tiene equipos
# de 3 a 15 anos: ponerles esa figura no produce "el nino", produce un adulto con su cara.
# Aqui se generan cuerpos por tramo de edad, con VARIAS variantes por tramo para que no salgan
# todos identicos, y con la misma equipacion (rayas verdes y blancas) que la figura de adulto.
#
# "plain ... no logos, no badges, no text": Flux se inventa escudos y patrocinadores si le dejas.
# El escudo y el patrocinador reales se pegan despues, en finish_ninos.py.
set -u
cd ~/ai-image-gen && source venv/bin/activate
OUT=~/ai-image-gen/ninos; mkdir -p "$OUT"

BASE="full body studio photograph of a young boy soccer player standing straight, facing the camera, arms relaxed at the sides, wearing a plain green and white vertical striped soccer jersey with no logos and no text and no badges, plain green shorts, green socks, white soccer boots, plain solid white background, sharp focus, soft studio lighting, the ENTIRE body visible from head to toe, centered, single person alone"

gen () {
  local nombre="$1" seed="$2" extra="$3"
  rm -f "$OUT/raw_$nombre.png"
  echo "[ninos] $nombre  ($(date +%T))"
  mflux-generate --model dhairyashil/FLUX.1-schnell-mflux-4bit --base-model schnell \
    --steps 8 --height 1440 --width 800 --seed "$seed" \
    --prompt "$BASE, $extra" --output "$OUT/raw_$nombre.png" >/dev/null 2>&1 \
    && echo "[ninos] OK $nombre" || echo "[ninos] FALLO $nombre"
}

# Tramo 6-9 (bebe, pre-benjamin, benjamin): cabeza grande respecto al cuerpo, tronco corto.
gen peque_a 5101 "he is 8 years old, small child with child body proportions, large head relative to a small short body, short dark brown hair"
gen peque_b 5102 "he is 7 years old, small child with child body proportions, large head relative to a small short body, short light brown hair"
gen peque_c 5103 "he is 9 years old, small child with child body proportions, large head relative to a small short body, short curly black hair"

# Tramo 10-13 (alevin, infantil): ya estirado pero sin masa muscular.
gen medio_a 5201 "he is 11 years old, preteen child body, thin and lanky with no muscle mass, short dark hair"
gen medio_b 5202 "he is 12 years old, preteen child body, thin and lanky with no muscle mass, short brown hair"

# Tramo 14-16 (cadete): adolescente, hombros aun estrechos.
gen ado_a 5301 "he is 15 years old, teenage boy, slim teenage build with narrow shoulders, short dark hair"
gen ado_b 5302 "he is 14 years old, teenage boy, slim teenage build with narrow shoulders, short light brown hair"

echo "[ninos] TERMINADO ($(date +%T))"
ls -la "$OUT"
