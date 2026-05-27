# Dependency audit playbook

Ejecutar en una rama separada antes de subir versiones, porque `Django`, `WeasyPrint`, `Pillow` y librerías de vídeo/PDF pueden tener cambios indirectos.

## Python

```bash
.venv/bin/python -m pip install --upgrade pip pip-audit
.venv/bin/pip-audit -r requirements.txt
.venv/bin/python -m pip list --outdated
```

Orden recomendado:

1. Parches compatibles de seguridad.
2. Librerías puras (`requests`, `urllib3`, `Pillow`) con tests completos.
3. `WeasyPrint` solo validando `system_healthcheck` y PDFs reales.
4. `Django` en commit propio con suite completa y smoke HTTP.

## Node/mobile

```bash
npm audit
cd mobile && npm audit
```

Si aparece un fix mayor, validar primero build web y app nativa. No aplicar `--force` sin revisar breaking changes.

## Cierre obligatorio

- `manage.py check`
- `manage.py system_healthcheck`
- `manage.py test football`
- `scripts/smoke_http_pages.py`
- revisión manual de PDF y Video Studio cuando cambien dependencias relacionadas
