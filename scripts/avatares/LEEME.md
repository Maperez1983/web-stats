# Figuras base de los avatares

Aquí está la receta para volver a fabricar los **cuerpos** de los avatares. Sólo hace falta si se
añade un tramo de edad, si cambia la equipación o si una figura sale mal; el día a día
(`manage.py generate_player_avatars`) no toca nada de esto.

Se ejecuta **en el Mac**, no en producción: usa Flux (`mflux`), `rembg` e `insightface`, que no
están —ni deben estar— en el servidor.

1. `bash gen_ninos.sh` — genera las figuras en bruto (~3 min cada una). `gen_bebes.sh` hace el
   tramo de 3-6 años (un niño de 4 no es un niño de 9: cabeza enorme y piernas cortas) y
   `gen_chandales.sh` el chándal de "a prueba" de cada tramo.
2. Míralas. Flux se inventa dorsales, escudos y a veces te cambia el color del pantalón; para
   repetir sólo las que salgan mal está `gen_ninos_repesca.sh`.
3. `python finish_ninos.py` — recorta el fondo, encaja cada figura en el lienzo de 651×1482 (el
   mismo que el adulto), **lleva el verde al verde del club** y pega el escudo y el patrocinador
   REALES. Lo del verde no es un capricho: Flux se inventa un verde distinto en cada tirada
   —salieron siete— y entonces cada niño llevaba una camiseta diferente, que era justo lo que no
   podía pasar. Se cambia tono y saturación conservando los pliegues; plano quedaría de cartón. Las posiciones se calculan
   respecto a la cara, no en porcentajes del lienzo: un niño tiene la cabeza mucho más grande y
   con porcentajes fijos el escudo le acaba en la barriga.
4. `python masks_figura.py <figura.png> <clave>` por cada figura de EQUIPACIÓN (los chándales no
   llevan máscaras: se sirven tal cual, no se les tiñe el pelo) — deduce las máscaras de pelo y de
   piel, que es lo que permite teñir el pelo del color del jugador.
5. `python montaje_figuras.py` — las pone en fila para mirarlas juntas.

Todo se escribe en `football/static/football/images/coach_roster_avatars/`. Con `WEBSTATS_REPO`
se elige a qué copia del repositorio.

El catálogo (qué cuerpo le toca a cada edad) vive en el código, en `FIGURAS` dentro de
`football/management/commands/generate_player_avatars.py`. Una figura sólo se usa si están en
disco su PNG y sus dos máscaras.
