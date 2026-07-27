"""Limpieza de accesos de la arquitectura anterior + arreglo de 2 roles (2026-07-27).

El cuerpo técnico ahora se crea SOLO desde el área Staff (ficha -> invitar por email). Había
accesos (WorkspaceMembership) creados con el sistema anterior que ensuciaban la lista de
miembros. Esta migración, en los workspaces de CLUB, borra las membresías que NO son del
propietario y se crearon ANTES de hoy (los 5 nuevos se crearon 2026-07-27). Además corrige el
rol global de Alonso (prep. portero) y Jeremías (prep. físico), que al reenviar la invitación
se había reseteado a 'entrenador'.

Dirigida y guardada: en BD frescas no hay esas membresías -> no borra nada.
"""
import logging
from datetime import date

from django.db import migrations

logger = logging.getLogger(__name__)

# Los 5 miembros válidos se crearon el 2026-07-27; todo lo anterior es arquitectura vieja.
_NEW_CUTOFF = date(2026, 7, 27)
_ROLE_FIXES = {
    "alonsogar_@hotmail.com": "preparador_portero",
    "jeremiaszaragoza@gmail.com": "preparador_fisico",
}


def _cleanup(apps, schema_editor):
    Workspace = apps.get_model("football", "Workspace")
    WorkspaceMembership = apps.get_model("football", "WorkspaceMembership")
    AppUserRole = apps.get_model("football", "AppUserRole")
    User = apps.get_model("auth", "User")
    try:
        for ws in Workspace.objects.filter(kind="club"):
            qs = (
                WorkspaceMembership.objects.filter(workspace=ws)
                .exclude(role="owner")
                .exclude(user_id=ws.owner_user_id)
                .filter(created_at__date__lt=_NEW_CUTOFF)
            )
            count = qs.count()
            if count:
                qs.delete()
                logger.info("Limpieza miembros legacy: workspace=%s borrados=%s", ws.id, count)
        for email, role in _ROLE_FIXES.items():
            for user in User.objects.filter(email__iexact=email):
                AppUserRole.objects.update_or_create(user_id=user.id, defaults={"role": role})
    except Exception:  # pragma: no cover - remediación puntual, no debe romper el deploy
        logger.exception("Limpieza de miembros legacy falló (no bloquea el deploy)")


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0193_appuserrole_email_verified_and_more"),
    ]

    operations = [
        migrations.RunPython(_cleanup, migrations.RunPython.noop),
    ]
