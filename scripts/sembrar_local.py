"""Siembra un club minimo en la base LOCAL para poder renderizar paginas al iterar.

Uso:  python3 scripts/sembrar_local.py

Idempotente. No maneja contrasenas: el usuario de desarrollo se crea con
set_unusable_password(), y las paginas se abren con force_login desde
scripts/ver_local.py. Nunca tocar una base que no sea la local.
"""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webstats.settings")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "dev-local")
os.environ.setdefault("ALLOW_SQLITE_IN_PROD", "true")
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from football.models import Team, Workspace, WorkspaceMembership, WorkspaceTeam

db = settings.DATABASES["default"]
if "sqlite" not in db.get("ENGINE", ""):
    raise SystemExit("Esto solo se ejecuta contra la base sqlite local. Abortado.")

User = get_user_model()
user, creado = User.objects.get_or_create(
    username="dev_local", defaults={"email": "dev_local@example.invalid", "is_staff": True, "is_superuser": True}
)
if creado:
    user.set_unusable_password()   # sin contrasena: solo se entra con force_login
    user.save()
elif not (user.is_staff and user.is_superuser):
    user.is_staff = user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])

team = Team.objects.order_by("id").first()
if not team:
    team = Team.objects.create(name="Equipo Local", slug="equipo-local")

ws, _ = Workspace.objects.get_or_create(
    slug="dev-local", defaults={"name": "Club Local", "kind": Workspace.KIND_CLUB, "primary_team": team}
)
if ws.primary_team_id != team.id:
    ws.primary_team = team
    ws.save(update_fields=["primary_team"])

WorkspaceTeam.objects.get_or_create(workspace=ws, team=team, defaults={"is_default": True})
WorkspaceMembership.objects.get_or_create(workspace=ws, user=user, defaults={"role": "owner"})

print(f"usuario: {user.username} (super) · workspace: {ws.slug} · equipo: {team.name} (id {team.id})")
