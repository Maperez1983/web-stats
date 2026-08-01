from pathlib import Path
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
client = Client(HTTP_HOST='127.0.0.1:8010')
client.force_login(user)
out = Path('tmp')
out.mkdir(exist_ok=True)
urls = [
    ('club', '/coach/sesiones/tarea/109/pdf/?html=1&style=club&live_preview_3d=1'),
    ('uefa', '/coach/sesiones/tarea/109/pdf/?html=1&style=uefa&live_preview_3d=1'),
    ('embed', '/coach/sesiones/tarea/109/pdf-3d-embed/?camera=analyst'),
    ('pdf', '/coach/sesiones/tarea/109/pdf/?style=club'),
]
for name, url in urls:
    response = client.get(url)
    suffix = '.pdf' if name == 'pdf' else '.html'
    path = out / f'task109_{name}{suffix}'
    path.write_bytes(response.content)
    print(name, response.status_code, path)
