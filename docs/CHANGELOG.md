# CHANGELOG

## 2026-07-13

### Documento táctico unificado

- Se ha empezado a transformar la pantalla de detalle/creación de tarea en un documento táctico único.
- La navegación principal de la tarea ahora expone de forma explícita `Ficha`, `Pizarra 2D`, `Vista 3D`, `Secuencia` y `Exportar`.
- `Vista 3D` y `Secuencia` ya se entienden como bloques del mismo documento, no como recorridos desconectados.

### Ficha Club

- La ficha Club incorpora un mapa del documento con estados visibles para `Ficha`, `Pizarra 2D`, `Vista 3D` y `Secuencia`.
- Se han añadido anclas internas para navegar a los bloques reales del documento.
- La zona de secuencia ya no desaparece cuando no hay escenas; muestra un estado pendiente claro.

### Timeline de secuencia

- La secuencia avanzada de la tarea ya no se muestra como una simple rejilla de imágenes.
- Se ha integrado una primera timeline editorial con rail vertical, pasos, duración, estado y previews por escena.
- La ficha Club muestra también una versión compacta de la secuencia para anticipar el storyboard sin salir del documento.
- La timeline ya puede gobernar la vista 3D: seleccionar paso, avanzar, retroceder y reproducir desde la propia ficha.
- El visor 3D publica el estado activo de paso y progreso para sincronizar la lectura del documento.
- La preview 2D principal ahora se sincroniza con la secuencia activa cuando existe snapshot por escena.
- La ficha muestra HUD vivo sobre la vista 2D con paso actual y progreso.

### Exportación viva

- La pestaña `Exportar` ya no funciona como una simple lista de enlaces.
- Se ha convertido en un bloque editorial del mismo documento, con preview viva de la tarea y estado de avance visible.
- La exportación refleja el paso activo de la secuencia, el título en curso y el porcentaje de progreso.
- Desde exportación ya se puede saltar directamente a `Vista 3D`, `Secuencia` y, cuando existe, a la edición gráfica real.

### Timeline táctica preparada para keyframes

- El motor de render de tarea ya deriva pistas por objeto a partir del timeline actual por snapshots.
- Cada tarea expone ahora número de `pistas`, `keyframes` y elementos con movimiento detectado sin duplicar estado.
- La ficha Club enseña esta lectura técnica dentro de la sección `Secuencia`.
- Se mantiene compatibilidad total con el timeline legacy; no se ha roto el flujo actual de escenas.
- Se añadieron tests unitarios específicos para la derivación de pistas en `football/test_render_timeline.py`.
- El editor 2D ya serializa también `simulation.pro` dentro del estado oficial de la tarea.
- Cuando existen tracks reales guardados desde `Timeline Pro`, la ficha los lee como fuente prioritaria en lugar de reconstruirlos solo por snapshots.
- El simulador ya muestra un inspector visible de `tracks` dentro de `Timeline Pro`, con recuento real de keyframes y foco por objeto.
- El entrenador puede filtrar el inspector a la selección activa y saltar desde cada track a sus keyframes sin salir del editor.

### Base técnica

- Se mantiene `tactical_layout` como fuente única del estado táctico en esta fase.
- No se ha introducido un segundo flujo ni un segundo modelo para 2D y 3D.
- Se ha validado la integridad básica con `manage.py check`.

### Cierre del módulo de tareas

- La ficha de tarea ya publica un `workbench` operativo con estado del motor único, readiness de 2D/3D/secuencia y resumen de jugadores/materiales.
- La capa de preview/IA ya queda visible dentro de la propia ficha mediante la preview generada disponible y un disparador directo de `IA táctica`.
- La exportación ya no depende solo de botones sueltos: ahora expone una matriz de salidas reales (`PDF Club`, `PDF UEFA`, `Preview PNG`, `Vista 3D`, `Canva / PPT`) con estado `Listo/Pendiente`.
- Todo lo anterior sigue colgado del mismo flujo `session-task-detail`, reforzando que la tarea se construye como documento único y no como recorridos paralelos.
- La sección `Secuencia` ya incluye inspector temporal de tracks dentro de la ficha: muestra objetos, keyframes, rango de pasos y si realmente hay movimiento.

### Editor Pro y cola persistente

- Se ha creado la nueva entrada `session-task-editor-pro` como shell premium del futuro editor modular.
- Ya existe una API unificada `session-task-editor-document-api` que expone la tarea como `TacticalDocument` único para 2D, 3D, secuencia, IA y exportación.
- Se añadió el modelo persistente `SessionTaskExportJob` con estados reales (`pending`, `running`, `done`, `error`, `canceled`) para empezar a sustituir exports directos sin trazabilidad.
- La ficha HTML ya enlaza a `Editor Pro` y enseña también los jobs recientes de exportación.
- Se ha creado el workspace `frontend/tactical-editor` con base React/TypeScript/Vite/Zustand para desacoplar el nuevo frontend del legacy Django template-driven.

### Editor Pro conectado a la pizarra real

- El documento del Editor Pro ya envía `graphic.canvas_state`, `canvas_width`, `canvas_height` y la URL oficial de guardado `session-task-graphic-save`.
- La vista central 2D ha dejado de ser una simple preview: ahora renderiza capas del `canvas_state` real y permite seleccionar y arrastrar objetos básicos sobre SVG.
- El botón `Guardar pizarra` ya persiste cambios contra el endpoint existente y recarga el documento unificado al terminar.
- El inspector muestra la selección activa y el frontend mantiene un estado `dirty/saving/error` explícito para el flujo de edición.

### Sincronización viva 2D → 3D

- La vista `3D` del Editor Pro ya incrusta el `embed 3D` oficial del sistema en lugar de una imagen estática.
- El runtime `session_task_detail_3d.js` ahora acepta sincronización por `postMessage` para reconstruir la escena desde un `canvas_state` recibido en vivo.
- El Editor Pro publica automáticamente el mismo estado compartido hacia la vista 3D embebida, evitando abrir un segundo motor desconectado.

### Generador editorial de imagen IA

- Se ha añadido un nuevo job persistente `ai_preview` dentro de `SessionTaskExportJob`.
- El sistema ya puede generar una portada editorial de tarea usando la pizarra real, el título, el objetivo, jugadores, materiales y dimensiones ya presentes en el documento.
- La imagen generada se guarda en `tactical_layout.meta.ai.generated_preview_data_v1` sin sobrescribir la preview gráfica base de la pizarra.
- Ya existe el endpoint dedicado `session-task-ai-preview-file` para servir esa imagen dentro de la ficha, el Editor Pro y la cola de exportación.
- El Editor Pro ya expone el botón `Generar imagen IA / Regenerar imagen IA` y refresca el documento al terminar.
- Si hay `OPENAI_API_KEY`, `Imagen IA` intenta primero generación real con OpenAI (`/images/generations`, modelo configurable con `OPENAI_IMAGE_MODEL`) y cae automáticamente al compositor editorial local si falla.
- La ficha unificada y el inspector exponen ya el proveedor/modelo usados para la imagen generada.
