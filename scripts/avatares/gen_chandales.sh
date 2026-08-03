#!/bin/bash
# Chándal por tramo de edad.
#
# El chándal que se usa para "a prueba" (chandal_black.png) es de adulto, y en este club casi
# todos los jugadores están a prueba: la pizarra de un equipo de benjamines se llenaba de hombres
# con chándal. El estado tiene que seguir viéndose —eso lo pidió el usuario expresamente— pero con
# el cuerpo de quien lo lleva.
#
# No llevan máscaras: estas figuras se sirven tal cual (no se les tiñe el pelo ni la piel), a
# diferencia de las de equipación.
set -u
cd ~/ai-image-gen && source venv/bin/activate
OUT=~/ai-image-gen/ninos; mkdir -p "$OUT"

BASE="full body studio photograph of a boy standing straight, facing the camera, arms relaxed at the sides, wearing a plain black sports tracksuit jacket with a zip and two thin white stripes down the sleeves, plain black tracksuit trousers, black sneakers, plain solid white background, sharp focus, soft studio lighting, the ENTIRE body visible from head to toe, centered, single person alone, no text anywhere, no logos, no badges"

gen () {
  local nombre="$1" seed="$2" extra="$3"
  rm -f "$OUT/raw_$nombre.png"
  echo "[chandal] $nombre  ($(date +%T))"
  mflux-generate --model dhairyashil/FLUX.1-schnell-mflux-4bit --base-model schnell \
    --steps 8 --height 1440 --width 800 --seed "$seed" \
    --prompt "$BASE, $extra" --output "$OUT/raw_$nombre.png" >/dev/null 2>&1 \
    && echo "[chandal] OK $nombre" || echo "[chandal] FALLO $nombre"
}

gen chandal_bebe  9101 "he is 5 years old, toddler body proportions, very big head compared to a very short body, short chubby legs, baby face, short dark hair"
gen chandal_peque 9102 "he is 8 years old, small child with child body proportions, large head relative to a small short body, short dark hair"
gen chandal_medio 9103 "he is 12 years old, preteen child body, thin and lanky with no muscle mass, short dark hair"
gen chandal_ado   9104 "he is 15 years old, teenage boy, slim teenage build with narrow shoulders, short dark hair"

echo "[chandal] TERMINADO ($(date +%T))"
