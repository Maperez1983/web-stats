# Definition of Done (cierre de producto) · 2J Football Intelligence

Fecha: 2026-05-01

Objetivo: que el sistema sea **estable**, **predecible** y **publicable** (App Store / Play Store), evitando regresiones (“antes funcionaba”).

Este repo empaqueta una web (`app.segundajugada.es`) dentro de una app (Capacitor). Por tanto, los P0 se centran en:
- navegación sin salida dentro de WebView
- autenticación persistente
- flujos críticos sin 400/404/500 por falta de contexto

## P0 (bloqueantes)

### P0.1 PDFs “sin salida” (iOS / app)
- Cualquier PDF se abre con overlay/visor con botón visible **Cerrar/Volver**.
- Si el servidor tarda en generar PDF, se muestra estado y se puede cerrar/cancelar.
- No existe ningún botón/enlace que dispare un PDF sin `match_id` válido (o sin contexto necesario).

### P0.2 Login persistente
- Cerrar y abrir la app => el usuario sigue logueado (salvo logout manual).
- Si expira sesión, se muestra login con mensaje (sin loops).

### P0.3 Contexto obligatorio (workspace/equipo)
- Si falta contexto, el sistema guía a onboarding/selector; nunca 404/500 por “equipo no configurado”.
- Guardrails para evitar mezclar categorías/equipos.

### P0.4 Importación (fidelidad)
- Importar **sesión/tarea PDF** guarda el PDF original y genera preview/card clicable (sin intentar reconstruirlo si no queda perfecto).
- (Pro) extracción asistida de tareas es opcional y nunca sustituye al PDF original.

### P0.5 Pizarra/chapas (drag & drop)
- En iPad/iPhone/desktop se pueden colocar recursos en cualquier punto del campo (sin offsets por scroll/zoom).

## P1 (market-ready)
- UX móvil: safe areas, imágenes no se cortan, botones “Back/Close” donde aplique.
- Partido: captura rápida (atajos) sin perder acciones actuales.
- Recomendador: tareas no repetidas y con el mismo formato que la biblioteca (consignas/normas/objetivos).

## Verificación obligatoria antes de subir
- Tests: `python manage.py test football`
- Smoke HTTP: `python scripts/smoke_http_pages.py`
- E2E Playwright (si hay credenciales/IDs): `node scripts/e2e_audit_playwright.js`

