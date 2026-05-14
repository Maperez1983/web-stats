# Auditoría exhaustiva — artefactos (2026-05-14)

Este directorio contiene salidas generadas automáticamente y resúmenes humanos para auditar el repositorio.

## Superficie HTTP

- `surface_urlpatterns.json`: mapa de rutas (webstats + football) → view + decoradores.
- `csrf_exempt_endpoints.md`: lista tabulada de endpoints con `csrf_exempt`.

Generación:
- `gen_surface.py`

## Búsqueda por patrones

- `pattern_hits.json`: hits por patrón (subprocess, requests, csrf_exempt, etc.).
- `pattern_hits.md`: resumen humano (muestra inicial por patrón).
- `deps_python_pinning.json`: dependencias pinneadas vs sin pin.

Generación:
- `gen_findings.py`

## SAST / CVEs

- `bandit.json`, `bandit.txt`: resultados Bandit sobre `football/`, `webstats/`, `scripts/`.
- `pip_audit_nodeps.json`: vulnerabilidades Python detectadas por `pip-audit`.
- `npm_audit.json`: vulnerabilidades Node detectadas por `npm audit`.
- `security_tool_summary.md` + `.json`: resumen agregado de Bandit y pip-audit.

Generación:
- `summarize_security_tools.py`

## Datos / privacidad

- `models_data_inventory.json`: inventario de subset de campos de modelos (Email/Date/File/Text/JSON…).
- `models_filefields.md`: tabla de `FileField`/`ImageField` y `upload_to`.
- `privacy_summary.md`: resumen y recomendaciones.

Generación:
- `gen_models_inventory.py`

