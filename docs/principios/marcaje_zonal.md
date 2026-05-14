# Marcaje zonal (sin balón) — conocimiento operativo

Este documento es una **guía operativa** para usar en scouting y para convertirlo en reglas/etiquetas dentro del Video Studio/AutoCut.

## 1) Qué es (definición práctica)

**Marcaje zonal**: los defensores priorizan la **ocupación de espacios/zona** y la **protección de zonas críticas** (líneas/pasos) en vez de seguir a un rival concreto todo el tiempo. Puede convivir con emparejamientos puntuales (mixto).

En ABP (córners/faltas laterales) suele significar:
- varios jugadores **fijos por zonas** (sobre todo en/entorno del área pequeña y primer palo/segundo palo)
- + algunos jugadores asignados a rivales específicos (híbrido/mixto)

## 2) Cómo reconocerlo en vídeo (checklist)

### A) ABP en contra (córner / falta lateral)

Indicadores visuales típicos de zonal:
- **Línea/arc** de defensores alineados en un carril (área pequeña/6-yard box) y/o
- Jugadores defendiendo **primer palo**, **zona central**, **segundo palo** sin “seguir” desmarques largos.
- Ajustes defensivos: pequeños pasos laterales para mantener la zona, no persecuciones largas.

Indicadores de mixto:
- 3–6 jugadores zonales (zona) + 2–5 jugadores claramente pegados a rivales (hombre).

Anti-ejemplos (NO concluyentes):
- Saque inicial, parones, saludos, publicidad, cambios, discusiones con árbitro.
- Cualquier clip donde no haya ABP real (no se va a ejecutar el balón parado).

### B) Defensa en juego (bloque medio/bajo)

En broadcast sin tracking, **no es fiable** separar “zonal” vs “al hombre” solo por movimiento de cámara.
Lo que sí es viable detectar como candidatos:
- “Bloque defensivo organizado” (líneas compactas) + basculación coordinada.

Para llegar a “zonal vs hombre” en juego necesitas 2 cosas:
- **Ejemplos etiquetados** en tus propios vídeos (semillas) y/o
- Tracking (jugadores/posesión), que ahora mismo AutoCut no tiene.

## 3) Taxonomía recomendada (para `principle`)

Propuesta de claves (string):
- `marcaje_zonal_abp_against`
- `marcaje_mixto_abp_against`
- `marcaje_hombre_abp_against`
- `bloque_defensivo_organizado`
- `basculacion_bloque`

Regla: usar además `phase`:
- `phase=abp_against` para ABP en contra
- `phase=defense` para defensa en juego

## 4) Cómo “enseñar” a AutoCut (metodología)

1. En Video Studio, crea eventos en Timeline con:
   - `Fase = abp_against` o `defense`
   - `Principio = marcaje_zonal_abp_against` (o el que toque)
2. Marca 3–8 ejemplos claros (no hace falta que sean perfectos).
3. Ejecuta AutoCut con **“Usar ejemplos del timeline”**.
4. Repite 1–2 rondas: corrige ejemplos, y AutoCut irá encontrando similares.

## 5) Limitaciones actuales (honestas)

- Sin tracking, el sistema no puede garantizar “zonal” vs “hombre” en juego abierto.
- En ABP sí se puede aproximar, pero requiere filtrar bien: evitar saques/parones/publicidad.

