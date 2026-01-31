# Web-stats

CRM para un equipo de futbol.

## Arranque rapido (local)

1) Crear entorno virtual y dependencias:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Inicializar proyecto Django:

```
./scripts/init_project.sh
```

3) Migraciones y servidor:

```
python3 manage.py migrate
python3 manage.py runserver
```

## Arranque con Docker

```
docker compose up --build
```

La app quedara en http://localhost:8000
