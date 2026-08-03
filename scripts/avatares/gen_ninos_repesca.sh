#!/bin/bash
# Segunda pasada para las figuras que salieron con algo que no toca.
#
# Flux se inventa cosas aunque le digas que no: en la primera tanda salieron un dorsal pintado en
# el pecho y unos calcetines de dos colores distintos. Se repiten SOLO esas, con la instruccion
# repetida y otra semilla; las que salieron bien no se tocan (cada tirada tarda tres minutos).
set -u
cd ~/ai-image-gen && source venv/bin/activate
OUT=~/ai-image-gen/ninos; mkdir -p "$OUT"

BASE="full body studio photograph of a young boy soccer player standing straight, facing the camera, arms relaxed at the sides, wearing a plain green and white vertical striped soccer jersey, plain green shorts, both socks exactly the same solid green, white soccer boots, plain solid white background, sharp focus, soft studio lighting, the ENTIRE body visible from head to toe, centered, single person alone, no jersey number, no numbers, no text anywhere, no logos, no badges, no sponsor"

gen () {
  local nombre="$1" seed="$2" extra="$3"
  rm -f "$OUT/raw_$nombre.png"
  echo "[repesca] $nombre  ($(date +%T))"
  mflux-generate --model dhairyashil/FLUX.1-schnell-mflux-4bit --base-model schnell \
    --steps 8 --height 1440 --width 800 --seed "$seed" \
    --prompt "$BASE, $extra" --output "$OUT/raw_$nombre.png" >/dev/null 2>&1 \
    && echo "[repesca] OK $nombre" || echo "[repesca] FALLO $nombre"
}

gen peque_a 7101 "he is 8 years old, small child with child body proportions, large head relative to a small short body, short dark brown hair"
gen medio_b 7202 "he is 12 years old, preteen child body, thin and lanky with no muscle mass, short brown hair"
gen peque_c 7103 "he is 9 years old, small child with child body proportions, large head relative to a small short body, short curly black hair"

echo "[repesca] TERMINADO ($(date +%T))"
