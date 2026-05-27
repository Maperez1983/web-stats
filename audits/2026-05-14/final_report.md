# Informe final (auditoría “exhaustiva”) — Web-stats — 2026-05-14

Este informe consolida:

- revisión manual (settings/boot/auth/billing/vídeo/IA/scraping),
- mapeo de superficie HTTP,
- búsquedas por patrones,
- SAST (Bandit),
- auditoría de dependencias (pip-audit + npm audit),
- inventario de datos/privacidad.

Artefactos y cómo reproducirlos: `audits/2026-05-14/README.md`.

## 1) Resumen de resultados (medible)

Superficie HTTP:
- `surface_urlpatterns.json`: **261** rutas detectadas (webstats+football).
- Endpoints con `csrf_exempt`: **1** tras hardening (ver `csrf_exempt_endpoints.md`).

SAST / CVEs:
- Bandit: **882** issues (mayoría LOW; ver `bandit.txt` / `bandit.json` + `security_tool_summary.md`).
- pip-audit: **49** vulnerabilidades en **7** paquetes (ver `pip_audit_nodeps.json` + `security_tool_summary.md`).
- npm audit: **0** vulnerabilidades (ver `npm_audit.json`).

## 2) Hallazgos críticos (P0/P1/P2)

### P0 (bloqueantes / alto riesgo)

1) `DATABASES` se define dos veces en `webstats/settings.py`
- Impacto: overrides silenciosos; riesgo de perder opciones (p. ej. `ssl_require`, `conn_max_age`) y divergencia entre “lo que crees” y “lo que corre”.
- Estado: corregido; queda un único bloque de configuración de BD.

### P1 (alto impacto, corregir pronto)

2) `csrf_exempt` demasiado extendido
- Estado: corregido para endpoints internos; solo queda el webhook externo de Stripe.
- Acción restante: si aparecen clientes sin cookies, usar tokens explícitos por workspace/usuario.

3) Dependencias Python con vulnerabilidades conocidas (pip-audit)
- Paquetes con mayor impacto por volumen de findings: `pypdf`, `django`, `urllib3`, `pillow`, `requests`, `weasyprint`, `yt-dlp`.
- Acción: plan de upgrades (con tests) y pinning estricto.

4) Superficie de DoS por procesamiento de vídeo/OCR (FFmpeg/Tesseract/WeasyPrint)
- Muchas rutas usan `subprocess` y trabajo pesado dentro del request/worker.
- Acción:
  - estandarizar ejecución (timeouts, `-nostdin`, `-hide_banner`, `-loglevel error`, limitar salida capturada),
  - mover trabajos largos a background jobs si el uso crece,
  - rate-limits/cuotas por workspace para endpoints pesados.

5) Posible SSRF si URLs externas son configurables sin allowlist estricta
- Acción: allowlist del host/esquema + bloqueo de IPs privadas/loopback.

### P2 (medio; mejora operación y reduce riesgo futuro)

6) Desalineación de versiones Python (local 3.9 vs runtime 3.11)
- Acción: unificar (ideal: dev en 3.11 para reproducibilidad).

7) Dependencias no 100% reproducibles
- Acción: pin completo (incluyendo `yt-dlp`) y/o lock con hashes.

8) Privacidad/PII: documentos y campos sensibles
- Hay `dni/phone/email/birth_date` y documentos (`licenses/`, `certifications/`, `match-reports/`).
- Acción:
  - definir retención, borrado y permisos por workspace/rol,
  - minimizar datos enviados a terceros (IA),
  - asegurar separación de media por tenant y validación de ownership.

## 3) Recomendación de roadmap (orden sugerido)

1) Upgrade de dependencias con CVEs (empezar por `django`/`requests`/`urllib3`/`pypdf`).
2) Completar hardening de trabajos pesados con colas si el uso crece.
3) Mantener allowlists de scraping/URLs externas al añadir nuevos proveedores.
4) Política de datos (retención, exportación, auditoría de accesos).

## 4) Notas de interpretación (para no “sobre-reaccionar”)

- Bandit reporta muchos issues LOW (p. ej. `try/except/pass`), útiles como señal de “zonas a revisar”, pero no equivalen 1:1 a vulnerabilidades explotables.
- pip-audit sí es accionable: cada finding corresponde a un advisory conocido, pero hay que validar si aplica a tu uso real (y si es transitive/direct).
