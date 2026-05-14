# Privacidad y datos (inventario + riesgos) — 2026-05-14

## Qué datos maneja la app (según modelos)

En `football/models.py` aparecen datos personales identificables (PII) y documentos:

- Staff: `dni`, `phone`, `email`, `birth_date` + documentos subidos (`federation_license`, `certification_document`).
- Jugadores: datos de identidad/deportivos (y potencialmente fechas/años de nacimiento).
- Documentos/archivos: actas/informes y adjuntos (`match-reports/`, licencias, certificados, etc.).
- Contenido generado por usuarios: tareas/sesiones con texto libre (puede contener PII si el club lo introduce).

Inventarios generados:

- `audits/2026-05-14/models_data_inventory.json`
- `audits/2026-05-14/models_filefields.md` (tabla de FileField/ImageField y `upload_to`)

## Flujos a terceros (procesadores)

1) Stripe (billing)
- Se usa Stripe para Checkout/Portal y webhook (`stripe/webhook/`).
- Riesgo típico: registros de eventos y estados de suscripción (bajo impacto de PII si solo IDs).

2) OpenAI (IA análisis de vídeo)
- Endpoint `analysis_video_studio_ai_api` construye un payload con títulos/etiquetas/notas de clips + timeline.
- Esto puede contener texto libre (notas) que potencialmente incluya PII (nombres, etc.) si el usuario lo escribe.
- Recomendaciones:
  - Minimizar/filtrar PII antes de enviar (p. ej. truncar o eliminar campos no necesarios).
  - Documentar explícitamente en Términos/Política qué datos se envían.
  - Añadir “modo privacidad” por workspace (desactivar IA o enviar solo datos anonimizados).

3) S3 (media, opcional)
- Cuando `USE_S3_MEDIA=true`, media pasa a S3.
- Recomendaciones:
  - Asegurar bucket privado + presigned URLs (ya hay soporte con `AWS_QUERYSTRING_AUTH`).
  - Definir política de retención y lifecycle rules (vídeos grandes).

## Exposición de archivos / control de acceso

- `webstats/media.py` sirve `/media/` con `login_required` y soporta `Range` (necesario para iOS/Safari).
- Aun así, el control real depende de:
  - que los ficheros en `MEDIA_ROOT` no se mezclen entre tenants/workspaces, y
  - que las rutas a ficheros privados no sean adivinables o accesibles por usuarios de otro workspace.

Recomendaciones:

- Para ficheros sensibles: usar rutas por workspace/equipo o IDs no enumerables, y validar ownership en views que exponen `FileField`.
- Considerar firmar/expirar enlaces si hay compartición externa.

## Logging

Hay bastantes `logger.exception(...)` en `football/views.py`. En general eso es bueno para observabilidad, pero revisa:

- no loguear `request.body` completo en endpoints con uploads,
- evitar loguear tokens/headers `Authorization`,
- evitar loguear documentos/PII (dni, teléfono, email) salvo necesidad.

## Retención y borrado

No he visto (aún) una política explícita de retención/borrado (p. ej. borrar vídeos tras X días).

Recomendaciones:

- Añadir retención configurable por workspace para:
  - vídeos/exports temporales,
  - documentos importados,
  - logs/artefactos de IA.
- Implementar borrado “seguro” (soft-delete + purge) donde aplique.

