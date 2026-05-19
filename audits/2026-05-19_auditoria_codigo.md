# Auditoría de código (Web-stats) — 2026-05-19

Repo: `Web-stats` (Django + frontend estático)

Objetivo: diagnosticar causas probables de inestabilidad (502 / pantallas en blanco / “no se puede cargar el editor”), priorizar riesgos y proponer acciones **sin romper lo que ya funciona**.

---

## 0) Resumen ejecutivo (priorizado)

### P0 — Riesgo alto / impacta producción
1) **Tácticas/TPad: bloqueo de JS en Safari por `ReferenceError`**
   - Síntoma: “No se puede cargar el editor” + consola: `ReferenceError: Can't find variable: isTacticsMode`.
   - Causa: `isTacticsMode` se referenciaba fuera de scope en `football/templates/football/task_builder.html`.
   - Estado: **corregido** en `ecbe0fa` (“Fix task builder: define isTacticsMode in outer scope”).
   - Acción: verificar despliegue en prod (ver sección 6).

2) **Procesos externos (ffmpeg/ocr/etc.) ejecutados dentro de requests sin timeouts consistentes**
   - Riesgo: un `subprocess.run/Popen` colgado bloquea workers → 502, timeouts, reinicios.
   - Estado: se añadió un guardrail concreto en kit2d (timeout ffmpeg) en `aff7d71`.
   - Acción recomendada: estandarizar helper con `timeout` + límites por endpoint y, a medio plazo, mover “render/export/análisis” a background jobs.

3) **Concurrencia/memoria en Render (workers)**
   - El stack carga librerías pesadas (numpy/opencv/playwright opcional). Con `--workers=2` aumenta riesgo de OOM en planes con RAM limitada.
   - Acción: medir OOM en logs; si existe, bajar workers a 1 y compensar con caching/colas.

### P1 — Seguridad / control de acceso (alto pero no necesariamente rompe hoy)
1) **Uso amplio de `@csrf_exempt` en endpoints autenticados**
   - Mitigación parcial actual: cookies SameSite=Lax + `login_required`.
   - Acción: ir retirando `csrf_exempt` donde no sea imprescindible (preferencias, uploads internos) y asegurar que frontend manda `X-CSRFToken`.

2) **Serving de `/media/` por path con login-only**
   - `webstats/media.py` protege con `login_required`, pero no aplica permisos por objeto: un usuario autenticado podría intentar adivinar rutas.
   - Acción: migrar media a S3 (presigned URLs) o servir solo rutas “no adivinables” y/o checks por objeto.

3) **Signup público sin rate-limit/captcha (si está activo)**
   - Está gated por `ENABLE_PUBLIC_SIGNUP`, pero si se activa: riesgo de spam/costos.
   - Acción: rate-limit y/o captcha.

### P2 — Mantenibilidad / deuda técnica (impacto gradual)
1) `football/views.py` es monolítico (decenas de miles de líneas) → alto riesgo de regresiones y difícil testear.
2) Falta de tests E2E/smoke para Tácticas (carga de editor, persistencia de superficie, guardado de clips).

---

## 1) Cambios aplicados en esta auditoría (sin romper)

1) Guardrails en kit2d (estabilidad / DoS accidental)
   - `football/kit2d_views.py`: límite de tamaño de subida (por env `KIT2D_MAX_UPLOAD_MB`, default 20MB) → HTTP 413 si excede.
   - `football/kit2d_generator.py`: `timeout=12` en ffmpeg fallback para HEIC (evita colgado).
   - Commit: `aff7d71` — “kit2d: guardrails for upload size and ffmpeg timeout”.

2) Fix crítico en Tácticas (Safari)
   - `football/templates/football/task_builder.html`: define `isTacticsMode` en scope superior para que Safari no rompa el script.
   - Commit: `ecbe0fa`.

---

## 2) Superficie de despliegue (Render)

Archivos clave:
- `render.yaml`: `startCommand: ./start_asgi.sh`, `healthCheckPath: /healthz`.
- `build.sh`: instala deps, (opcional) playwright browsers en build, `collectstatic`, crea `media/`.
- `start_asgi.sh`: migra con reintentos y “fail-open” en Render, arranca gunicorn (WSGI por defecto) y habilita logs a stdout.

Observación:
- Playwright **no** debería instalar browsers en runtime (se desaconseja). Revisar variables:
  - `INSTALL_PLAYWRIGHT_BROWSERS=false`
  - `INSTALL_PLAYWRIGHT_BROWSERS_AT_RUNTIME=false`

---

## 3) Hotspots detectados (backend)

### 3.1 Subprocess / binarios externos (riesgo P0)
Rutas/módulos con uso de ffmpeg/tesseract/opencv:
- `football/video_autocut.py` (Popen sin timeout).
- `football/views.py` (múltiples `subprocess.run/Popen`, muchos sin `timeout=`).
- `football/kit2d_generator.py` (ffmpeg fallback: ahora con timeout).

Riesgo operativo:
- Un vídeo corrupto, un binario ausente o un proceso “pegado” puede dejar un worker bloqueado hasta `gunicorn --timeout`.

Recomendación:
- Centralizar ejecución en helper: `run_subprocess(cmd, timeout_s, ...)` con:
  - `timeout` obligatorio
  - captura acotada de stderr (para debug)
  - límites de tamaño/frames
  - mensajes de error “user friendly”

### 3.2 Endpoints pesados dentro de requests (riesgo P0/P2)
“Exportar”, “OCR”, “render server”, “autocut”, etc. se ejecutan como request síncrona.
Recomendación:
- a medio plazo: job queue (Celery/RQ) + polling
- a corto plazo: timeouts estrictos + 202 + “export job” ya existe en parte del sistema

---

## 4) Frontend Tácticas/TPad (hallazgos)

1) El editor depende de carga de `fabric` + stack TPad; si el script inline se rompe, no hay fallback.
2) El código ya intenta **evitar que “Guardar clip” cambie la superficie**, capturando/restaurando metadatos:
   - `capturePitchMetaForStep()` / `applyPitchMetaFromStep()`
   - `pitchPreset` se usa como fuente de verdad para evitar fallbacks a `full_pitch` durante modales/resizes.
3) El bug bloqueante reportado (`isTacticsMode`) era suficiente para dejarlo inutilizable en Safari.

Recomendación inmediata:
- Tras despliegue del fix, si persiste: capturar en DevTools:
  - Network 200/404 de `/static/vendor/fabric.min.js`
  - Network 200/404 de `/static/football/js/sessions_tactical_pad.js`
  - errores de consola (primero que aparezca).

---

## 5) Seguridad (resumen)

1) Sanitización HTML: existe `_sanitize_task_rich_html` (parser allowlist) → bien (reduce XSS).
2) `@csrf_exempt`: listado completo (ver tabla en sección 5.2). Muchos endpoints autenticados lo usan.
3) `/media/` protegido por login, pero no por objeto.
4) Signup público depende de env.

### 5.1 Recomendación gradual de CSRF
Prioridad:
1) Preferencias (`workspace_preference_set_api`)
2) Uploads internos de recursos (`pdf_graphic_asset_upload`)
3) Pages con POST (task builder / sessions task create/edit)

Plan de transición:
- Asegurar `X-CSRFToken` siempre en fetch.
- Quitar `@csrf_exempt` endpoint a endpoint, con feature flag si hace falta.

### 5.2 Endpoints con `@csrf_exempt` (extracto)
- Stripe: `stripe_webhook` (correcto; valida firma).
- Autenticados: `workspace_preference_set_api`, `pdf_graphic_asset_upload/delete`, módulo análisis (varios), playbook clips (varios), etc.

---

## 6) Verificación rápida en producción (checklist)

1) Confirmar build actual:
   - abrir `https://app.segundajugada.es/build/` y comprobar `build.id`.
2) Confirmar que el template nuevo está en producción:
   - en Safari: recargar duro + vaciar cache del Service Worker si aplica.
   - revisar consola: el `ReferenceError isTacticsMode` debe desaparecer.
3) Si el editor sigue en blanco:
   - Network: comprobar carga de `fabric.min.js` y `sessions_tactical_pad.js` (status 200).
   - si hay 502/404: revisar collectstatic/whitenoise y manifest.

---

## 7) Recomendaciones (lista accionable)

### P0 (esta semana)
- Monitorizar logs de Render buscando OOM/worker timeouts.
- Añadir `timeout=` a subprocess críticos en endpoints de uso frecuente.
- Asegurar despliegue del fix de Tácticas y limpiar caches.

### P1 (próximas 2–4 semanas)
- Retirar `csrf_exempt` en endpoints internos de forma progresiva.
- Endurecer serving de `/media/` (S3 presigned o verificación por objeto).

### P2 (meses)
- Dividir `football/views.py` por dominios (dashboard, actions, tactics, academy, analysis).
- Añadir tests de smoke del editor TPad (carga + cambiar superficie + guardar clip + recargar y verificar persistencia).

