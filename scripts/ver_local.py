"""Renderiza una pagina del producto en LOCAL sin desplegar ni tocar contrasenas.

Uso:  python3 scripts/ver_local.py /coach/plantilla/ [busqueda]

Usa el cliente de pruebas de Django con force_login sobre un usuario que YA existe
en la base local: no crea cuentas ni introduce credenciales. Sirve para iterar en
segundos (marcado, contraste, estructura) y dejar produccion solo para la
comprobacion final.
"""
import os, sys, re, django

# El script vive en scripts/, asi que hay que poner la raiz del proyecto en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webstats.settings")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "dev-local")
os.environ.setdefault("ALLOW_SQLITE_IN_PROD", "true")
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

ruta = sys.argv[1] if len(sys.argv) > 1 else "/coach/"
buscar = sys.argv[2] if len(sys.argv) > 2 else ""

User = get_user_model()
user = (User.objects.filter(username="dev_local").first()
        or User.objects.filter(is_superuser=True).order_by("id").first()
        or User.objects.order_by("id").first())
if not user:
    print("La base local no tiene usuarios: no se puede renderizar nada autenticado.")
    raise SystemExit(1)

c = Client()
c.force_login(user)
r = c.get(ruta, secure=True, HTTP_HOST="localhost")
html = r.content.decode("utf-8", "ignore")
print(f"{ruta}  ->  HTTP {r.status_code}  ({len(html)} bytes)  usuario: {user.username}")
if r.status_code in (301, 302):
    print("  redirige a:", r.headers.get("Location"))
if buscar:
    n = len(re.findall(re.escape(buscar), html))
    print(f"  '{buscar}': {n} coincidencia(s)")
