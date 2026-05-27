# Background jobs roadmap

Objetivo: sacar de request/response las operaciones que pueden bloquear workers web o agotar timeouts.

## Candidatos prioritarios

1. Video Studio: ffmpeg/ffprobe, export de clips, playlists, voz en off y autocut.
2. PDFs: informes de jugador/equipo y exports de análisis con WeasyPrint.
3. Sincronizaciones externas: Universo/RFAF/La Preferente y scraping de plantillas.
4. OCR/visión: análisis de vídeo y lectura de frames.

## Contrato mínimo de job

- `id`, `kind`, `status`: `queued|running|done|error|cancelled`.
- `workspace_id`, `team_id`, `owner_user_id`.
- `input`: JSON pequeño con ids internos, nunca rutas arbitrarias de usuario.
- `progress`: porcentaje o fase textual.
- `result`: JSON con ids/URLs generadas.
- `error`: mensaje corto para UI y detalle completo solo en logs.

## Guardrails

- Timeout por job según tipo.
- Idempotencia por `idempotency_key` en exports costosos.
- Reintentos solo en fallos transitorios de red, no en validación ni permisos.
- Logs con `job_id`, `workspace_id`, `team_id`, `user_id`.
- Limpieza periódica de temporales y exports caducados.

## Implantación recomendada

1. Crear modelo `BackgroundJob` y endpoints `create/status/cancel`.
2. Migrar primero export de playlists de Video Studio porque ya tiene endpoints de job.
3. Añadir worker separado en Render antes de mover PDFs.
4. Mantener fallback síncrono solo en `DEBUG`.
