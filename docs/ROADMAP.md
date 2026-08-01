# ROADMAP

## Estado actual

Fase en curso: transición desde ficha/pizarra separadas hacia un documento táctico único.

## Próximos módulos

### 1. Secuencia interactiva

- Refinar la timeline operativa con paso activo, reproducción y navegación temporal real.
- Unificar storyboard 2D, recreación 3D y exportación temporal.
- Añadir keyframes reales por objeto, no solo por escena.
- Sustituir la derivación automática de pistas por edición explícita de tracks desde la interfaz.
- Llevar el nuevo inspector visual de tracks desde `Timeline Pro` a una edición temporal todavía más directa fuera del simulador.

### 2. Motor gráfico único

- Reforzar la semántica de `Pizarra 2D` como editor fuente.
- Hacer más clara la relación entre pizarra guardada, preview 2D, vista 3D y secuencia.
- Mejorar el lanzador `Añadir pizarra` para que opere como selector de vistas del mismo documento.
- Terminar de retirar del todo las superficies legacy residuales del alta de tarea y dejar `session-task-detail` como entrada inequívoca.
- Migrar el shell `session-task-editor-pro` desde HTML servidor a bundle React/TS consumiendo la API unificada ya creada.

### 3. Vista 3D integrada

- Mejorar la incrustación del 3D dentro de la ficha para revisión rápida.
- Afinar cámaras, estado vacío, fallback y retorno visual a la ficha.
- Preparar el salto a un estadio 3D coherente con una sola estructura.

### 4. Exportación documental

- Conectar la exportación viva con colas reales para PDF, PowerPoint, PNG, GIF y vídeo.
- Generar estados de procesamiento, errores y reintentos desde la propia ficha.
- Usar la misma secuencia como fuente de presentación, exportación y futura animación automática.
- Convertir la actual matriz de salidas visibles en un verdadero panel de jobs con progreso y auditoría.
- En esta fase ya existe el modelo persistente `SessionTaskExportJob`; falta conectar workers reales para GIF/MP4/PPT.

### 5. Timeline profesional

- Sustituir la timeline actual por una línea de tiempo con keyframes, tracks y capas.
- Añadir control de duración, esperas, transiciones y reproducción parcial.
- Preparar la base para exportación a vídeo, GIF y presentación.

### 6. Arquitectura

- Seguir desacoplando el flujo legacy sin romper guardado ni exportación.
- Identificar los puntos donde `tactical_layout` debe evolucionar hacia un documento táctico más explícito.
- Preparar la migración futura a un frontend modular alineado con el `MASTER_PLAN`.
- Consolidar `session-task-editor-document-api` como contrato estable antes de encender el canvas React/Three definitivo.
