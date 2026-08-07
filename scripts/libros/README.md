# Meter en la biblioteca las tareas de un libro

Un libro de ejercicios trae, por página, una ficha de texto y un dibujo. Aquí está la
maquinaria para convertir eso en tareas de la biblioteca **con la pizarra editable**, no con
una foto pegada.

## El orden

1. **`leer_<libro>.py`** — saca la ficha de texto de cada página (`pdftotext` y luego partir
   por las etiquetas del libro). `leer_levelup.py` sirve de ejemplo: cada libro tiene sus
   propias etiquetas y hay que escribir esta parte.
2. **`crear_tareas.mjs`** — crea una tarea por ficha con su texto y su clasificación, y le
   sube **el dibujo del libro como portada**. Reanudable: lo ya creado se salta.
3. **`leer_dibujo.py`** — lee el dibujo: fichas por color, contorno, divisiones y balón.
4. **`leer_flechas.py`** — las flechas, para ejercicios tipo rueda de pases.
5. **`montar_pizarras.mjs`** — monta la pizarra en el editor real, elemento a elemento.
6. **`fotografiar.mjs`** — hace la foto HD de cada pizarra desde esta máquina.

## Lo que costó encontrar, y no es evidente

Cada una de estas reglas sustituye a otra que parecía razonable y era **falsa**:

- **El color de un equipo es el que MÁS PÍXELES tiene, no el más brillante.** Los halos que
  deja el JPEG alrededor de cada círculo son más claros que las fichas y se comían las plazas.
- **No hay una paleta única**: el mismo azul es (90,155,213) en un ejercicio y (42,119,165) en
  otro. Los colores se descubren en cada dibujo.
- **Una ficha es una mancha REDONDA (u ovalada) Y RELLENA.** Sin el relleno entran las letras
  de las estaciones; exigiendo círculo perfecto, los dibujos con fichas ovaladas devuelven
  cero fichas.
- **El troceado de fichas pegadas necesita tope.** Sin él, una mancha grande (el césped) se
  parte en cientos de jugadores: hubo un dibujo devolviendo 3.222.
- **Un rectángulo del dibujo es el que NINGUNA línea atraviesa por dentro.** Con "cuatro lados
  pintados" basta la unión de dos rectángulos pegados, y salían 20 donde había 7.
- **El contorno sólo se dibuja si está dibujado**: en los ejercicios con bandas alrededor el
  conjunto forma una CRUZ y las esquinas están vacías. Se comprueba mirando las esquinas.
- **Lo que el libro dibuja son SEPARACIONES, no zonas.** Una línea continua o discontinua NO
  es un recuadro amarillo: en este sistema un recuadro amarillo es una zona de intervención,
  que significa otra cosa.
- **El balón no se distingue por color ni por tamaño** (hay jugadores amarillos, y balones que
  miden lo mismo que un jugador): se busca por su icono, blanco con manchas negras, uniendo
  los trozos en que sus propias manchas lo parten.
- **Las flechas no se buscan como líneas sueltas**: unen estaciones, así que se prueba el
  camino recto entre cada par, con varias salidas alrededor de cada una.

## Del editor

- Zonas, líneas, flechas y formas **no hacen caso al arrastre**: crean el objeto del tamaño
  por defecto donde les parece. Hay que crearlas y **colocarlas después por dato**.
- Se crean en el MARGEN: arrastrando por el centro, el gesto empieza encima de una ficha ya
  puesta y el editor la selecciona en vez de crear.
- Los rótulos de texto no se crean con un clic programado: hay que construir el mismo objeto
  que crea el editor (`fabric.IText` con `data.kind='text'`).

## Y lo importante

La ficha enseña **el dibujo del libro** hasta que alguien abre la tarea, la corrige y la
guarda. Una recreación automática con un fallo tonto es peor que no tenerla.
