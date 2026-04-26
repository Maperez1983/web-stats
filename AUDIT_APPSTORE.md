# Auditoría completa (App Store) · 2J Football Intelligence

Fecha: 2026-04-26

Objetivo: dejar una **lista cerrada** de arreglos/ajustes **sí o sí** antes de enviar a **App Store Review**, y un checklist por pantallas para validar en local + TestFlight.

Este repo empaqueta una **web remota** (`https://app.segundajugada.es`) dentro de una app **Capacitor** (`mobile/`). Por tanto, para App Store lo crítico es:
- estabilidad y navegación dentro de WebView (sin “pantallas sin salida”)
- autenticación persistente
- PDFs/vídeos descargables/compartibles sin bloquear la app
- coherencia de datos por categoría (no mezclar Senior/Prebenjamín)

---

## Cómo reproducir y auditar en local

Servidor Django:
```bash
cd Web-stats
DEBUG=true SECRET_KEY=dev ALLOW_SQLITE_IN_PROD=true .venv/bin/python manage.py runserver 127.0.0.1:8000
```

Auditoría E2E (Playwright) con contexto de club:
```bash
cd Web-stats
E2E_BASE_URL=http://127.0.0.1:8000 \
E2E_USERNAME=admin E2E_PASSWORD=admin \
E2E_WORKSPACE_ID=11 E2E_TEAM_ID=80 \
node scripts/e2e_audit_playwright.js
```

Salida:
- `Web-stats/artifacts/e2e-audit/<timestamp>/report.json` (detalle)
- `Web-stats/artifacts/e2e-audit/<timestamp>/summary.json` (resumen)

Notas:
- El E2E evita rutas destructivas (delete/reset/save finales) pero sí crea datos “de prueba” en algunos flujos.
- PDFs disparan descargas (esto en Playwright se reporta como “download is starting”).

---

## Estado actual (snapshot de auditoría)

E2E más reciente: `artifacts/e2e-audit/2026-04-26T18-56-46-964Z/report.json`

Errores detectados por E2E (los que quedan son mayormente **PDFs sin parámetros** o **IDs que no existen**):
- `/player/<id>/` (404 si el `player_id` no existe en el equipo activo)
- `/player/<id>/pdf/` (503 si el jugador no existe)
- `/convocatoria/pdf/` (400 si no hay match/convocatoria “actual”)
- `/convocatoria/*/pdf/` (400 si `match_id` no corresponde)

Esto es importante porque en la app real **no debe existir ningún botón** que dispare un PDF sin `match_id` válido, ni enlaces a un jugador inexistente.

---

## Checklist por pantallas (qué validar)

### 1) Login / Sesión / Onboarding
- [ ] La sesión se mantiene al cerrar y abrir la app (no pide credenciales cada vez).
- [ ] Si falta contexto (workspace/equipo), redirige a onboarding/selector (no 404/500).
- [ ] Existe “Salir” (logout) en un lugar claro (menú o Ajustes).
- [ ] Si la suscripción está inactiva, se muestra paywall sin romper navegación.

### 2) Dashboard (Portada)
- [ ] No mezcla categorías (guardrail: rival/standing incoherente => aviso + link a configuración).
- [ ] Botón “Actualizar” no se queda pillado (feedback y timeout).
- [ ] Datos básicos visibles con equipo activo.

### 3) Jugadores
- [ ] Lista carga sin duplicados raros ni partidos repetidos.
- [ ] Vista de jugador: KPIs por partido y totales coherentes.
- [ ] PDF de jugador se abre en overlay (cerrar/back funciona).

### 4) Partido (hub) + Registro de acciones
- [ ] Crear partido => guardar => registrar acciones => ver KPIs del partido.
- [ ] Guardados persisten al salir y entrar.
- [ ] Si no hay partido activo, la UI guía (no pantallas vacías).

### 5) Convocatoria + 11 inicial
- [ ] Convocatoria guarda y asigna `match_id` correcto.
- [ ] PDF Convocatoria / Árbitro solo aparece si hay `match_id` válido.
- [ ] En iPad/iPhone el PDF no bloquea la app (overlay con “Cerrar”).

### 6) Entrenos (Sesiones / Biblioteca / Importar)
- [ ] Biblioteca organizada por: tareas / sesiones / microciclos (y por “Tradicional” vs “Interactiva”).
- [ ] Importar **sesión PDF**: se guarda “tal cual” y la card usa preview del PDF.
- [ ] Importar **tarea PDF**: se guarda “tal cual” y la card usa preview del PDF.
- [ ] Editor pizarra: se pueden colocar chapas en todo el campo (sin margen lateral).
- [ ] Orden lógico de bloques (Calentamiento → Activación → Principal 1 → Principal 2 → Vuelta a la calma).
- [ ] PDF de sesión: no recorta campos, mantiene orden y centrado de representación gráfica.

### 7) Informes + KPIs avanzados
- [ ] Se puede elegir KPI por cualquier acción registrada (tipo/resultado/zona/tercio).
- [ ] Export a PDF sin bloquear la app y con “Cerrar”.

### 8) Análisis (staff) + Vídeo
- [ ] Subida de vídeo (normal y chunked) y creación de carpeta.
- [ ] Video Studio: recortes (IN/OUT), telestración, timeline, slides.
- [ ] Export: PDF slides, ZIP, informe PDF.
- [ ] Compartir: enlaces (clip/playlist/informe) y envío a inbox.

### 9) Plataforma / Administración
- [ ] Selector de workspace/equipo (si aplica) funciona y evita mezclar datos.
- [ ] Usuarios/roles y staff directory coherentes por equipo.

---

## Lista cerrada (P0) · obligatorio antes de App Store

### P0.1 Navegación “sin salida” (PDFs)
**Problema:** en WebView iOS no hay barra de navegación; cualquier PDF abierto “a pantalla completa” puede dejar al usuario atrapado.

**Criterio de aceptación:**
- Cualquier PDF se abre en overlay con botones visibles: `Cerrar`, `Imprimir`, `Descargar`.
- “Cerrar” vuelve a la pantalla anterior sin recargar la app.
- Si el servidor tarda en generar PDF, se ve estado y se puede cancelar/cerrar.

### P0.2 Sesión persistente (login)
**Problema:** si cookies Secure/SameSite o backend/session se rompe, el usuario tiene que loguearse cada vez.

**Criterio de aceptación:**
- Cerrar app y reabrir => sigue logueado (salvo logout manual).
- Si expira sesión, se muestra login con mensaje (no loops raros).

### P0.3 Contexto obligatorio (workspace/equipo)
**Problema:** entrar a módulos sin “equipo activo” produce 400/404/500.

**Criterio de aceptación:**
- Si falta contexto, redirige a `Onboarding/Selector` (no 404/500).
- Un usuario técnico siempre cae a un club/equipo válido o a configuración.

### P0.4 Importación de sesiones/tareas (fidelidad del PDF)
**Problema:** se pierde estructura (texto cortado, desorden, por páginas) y la sesión importada no se representa como el ejemplo.

**Criterio de aceptación:**
- Importar sesión PDF guarda el PDF original, preview correcto, y acceso 1-click.
- (Opcional Pro) “extraer tareas” genera tareas separadas, pero sin romper el PDF original.

### P0.5 Pizarra / Chapas (drag & drop)
**Problema:** no deja colocar chapas en cualquier zona del campo (solo margen lateral).

**Criterio de aceptación:**
- En iPad/iPhone y desktop: se pueden soltar recursos en cualquier punto del campo.
- No hay offsets raros por scroll/zoom.

### P0.6 Clasificación/KPIs mezclando categorías
**Problema:** “Actualizar clasificación” puede mostrar datos de otra categoría (Senior vs Prebenjamín).

**Criterio de aceptación:**
- Guardrail: si rival/standing no coincide, avisar y no mezclar.
- Configuración de “Universo ID grupo” validada y visible para el admin.

---

## P1 (debería entrar antes de publicar, pero no bloquea si P0 está ok)

- Mejorar UI móvil: imágenes de portada no se cortan; safe areas; tamaños.
- Añadir botón “Atrás” global (solo en app) en cabecera para navegación consistente.
- Recomendador de tareas: evitar repetición, aumentar explicación (objetivos/consignas/normas) y ajustar al formato de la biblioteca.
- Selector de KPIs visual tipo “dashboard builder” (favoritos/presets por rol).
- Rendimiento: lazy-load de listas (vídeos, tareas), y evitar queries pesadas en home.

---

## P2 (roadmap pro)

- Editor tipo “lienzo” iPad (dedo/Apple Pencil) + reconocimiento de trazos (flecha → recurso).
- Tareas interactivas desde vídeo: extracción asistida (semi-automática) de fases + generación de animación de chapas.
- Analítica avanzada: constructor de KPIs a partir de “acciones registrables” (cualquier evento → KPI).
- Video analysis Pro: plantillas por rival, paquetes para staff, y librería compartida por partido.

