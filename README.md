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

Si esas dependencias no estan disponibles, la app sigue funcionando en partes del flujo, pero algunas exportaciones o capturas pueden degradarse.

## Arranque con Docker

```
docker compose up --build
```

La app quedara en http://localhost:8000
