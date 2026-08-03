#!/bin/bash
# Tramo BEBÉ (3-6 años).
#
# El primer catálogo metía de 0 a 9 años en el mismo saco, y un niño de 4 no tiene nada que ver
# con uno de 9: cabeza mucho más grande, tronco corto, piernas cortas. Este tramo es suyo.
set -u
cd ~/ai-image-gen && source venv/bin/activate
OUT=~/ai-image-gen/ninos; mkdir -p "$OUT"

BASE="full body studio photograph of a very young boy soccer player standing straight, facing the camera, arms relaxed at the sides, wearing a plain green and white vertical striped soccer jersey, plain green shorts, both socks exactly the same solid green, white soccer boots, plain solid white background, sharp focus, soft studio lighting, the ENTIRE body visible from head to toe, centered, single person alone, no jersey number, no numbers, no text anywhere, no logos, no badges, no sponsor"

gen () {
  local nombre="$1" seed="$2" extra="$3"
  rm -f "$OUT/raw_$nombre.png"
  echo "[bebe] $nombre  ($(date +%T))"
  mflux-generate --model dhairyashil/FLUX.1-schnell-mflux-4bit --base-model schnell \
    --steps 8 --height 1440 --width 800 --seed "$seed" \
    --prompt "$BASE, $extra" --output "$OUT/raw_$nombre.png" >/dev/null 2>&1 \
    && echo "[bebe] OK $nombre" || echo "[bebe] FALLO $nombre"
}

gen bebe_a 8101 "he is 4 years old, toddler body proportions, very big head compared to a very short body, short chubby legs, baby face, short blonde hair"
gen bebe_b 8102 "he is 5 years old, toddler body proportions, very big head compared to a very short body, short chubby legs, baby face, short dark hair"

echo "[bebe] TERMINADO ($(date +%T))"
