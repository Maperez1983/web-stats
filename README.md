# Web-stats

CRM para un equipo de futbol.

## Arranque rapido (local)

1) Crear entorno virtual y dependencias:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configurar entorno local:

```
cp .env.example .env
export DEBUG=true
export SECRET_KEY=dev-insecure-change-me
```

3) Inicializar proyecto Django:

```
./scripts/init_project.sh
```

4) Migraciones y servidor:

```
python3 manage.py migrate
python3 manage.py runserver
```

Si no exportas `DEBUG=true` o una `SECRET_KEY`, Django no arrancara.

Verificacion rapida del entorno:

```
python3 manage.py system_healthcheck
```

## Sesión y login (evitar re-login continuo)

Si la app te manda al login "a cada paso", casi siempre es porque el navegador **no está guardando** la cookie de sesión. Dos causas típicas:

- Estás entrando por `http://` pero en producción tienes `SESSION_COOKIE_SECURE=true` (la cookie no se guarda en HTTP).
- Estás en un despliegue con **más de una instancia** usando SQLite: la sesión en DB puede no ser compartida entre instancias.

Variables útiles:

```
# Si no tienes HTTPS (solo para entornos internos)
SECURE_SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false

# Si necesitas compartir sesión sin Redis (p. ej. varias instancias con SQLite)
# (en producción con SQLite esto ya se activa por defecto si no defines SESSION_ENGINE)
SESSION_ENGINE=django.contrib.sessions.backends.signed_cookies

# Evitar colisión con otras apps en el mismo dominio
SESSION_COOKIE_NAME=webstats_sessionid
CSRF_COOKIE_NAME=webstats_csrftoken

# Caducidad
SESSION_COOKIE_AGE=2592000          # 30 días
SESSION_SAVE_EVERY_REQUEST=false
```

## Bootstrap admin opcional

En entornos como Render, si quieres asegurar un admin tras `migrate`, puedes definir:

```
BOOTSTRAP_ADMIN_USERNAME=mperez
BOOTSTRAP_ADMIN_PASSWORD=una-clave-segura
BOOTSTRAP_ADMIN_EMAIL=tu@email.com
BOOTSTRAP_ADMIN_RESET_PASSWORD=false
```

Con eso la app creara el usuario si no existe. Si ya existe y quieres forzar una nueva clave, cambia `BOOTSTRAP_ADMIN_RESET_PASSWORD=true` durante un despliegue.

## Dependencias nativas opcionales

Algunos modulos avanzados requieren dependencias del sistema:

- `weasyprint`: generacion de PDFs
- `pytesseract`: OCR
- `playwright`: login/captura browser para Universo RFAF

Además, Playwright se puede usar para generar previews HD (WYSIWYG) del editor táctico:

- `TPAD_SERVER_RENDER_PREVIEW=true`: intenta renderizar previews HD en servidor (fallback automático si Playwright/browsers no están disponibles).
- `TPAD_SERVER_RENDER_PREVIEW_FORCE=true`: fuerza el render en cada guardado (más CPU).
- `INSTALL_PLAYWRIGHT_BROWSERS=true`: en `build.sh`, instala Chromium durante el build.

Si esas dependencias no estan disponibles, la app sigue funcionando en partes del flujo, pero algunas exportaciones o capturas pueden degradarse.

## Arranque con Docker

```
docker compose up --build
```

La app quedara en http://localhost:8000
