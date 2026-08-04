"""Los ojeados que ya existen son del equipo principal de su club.

Hasta ahora la dirección deportiva colgaba sólo del club, así que todos los objetivos se
crearon sin categoría. Si se quedan sin equipo, con el filtro nuevo seguirían viéndose desde
todas las categorías y no habríamos arreglado nada.

Se les asigna el equipo principal del workspace (el senior), que es de donde venían: es lo que
el usuario ve hoy al abrir Dirección. Los que ya tengan equipo no se tocan, y si un workspace
no tiene equipo principal se quedan como están (visibles en todas) antes que esconderlos.
"""

from django.db import migrations


def asignar_equipo_principal(apps, schema_editor):
    ScoutingTarget = apps.get_model('football', 'ScoutingTarget')
    Workspace = apps.get_model('football', 'Workspace')

    principal_por_workspace = {}
    for workspace in Workspace.objects.all().only('id', 'primary_team_id'):
        if getattr(workspace, 'primary_team_id', None):
            principal_por_workspace[workspace.id] = workspace.primary_team_id

    for target in ScoutingTarget.objects.filter(team__isnull=True).only('id', 'workspace_id', 'player_id'):
        equipo_id = principal_por_workspace.get(target.workspace_id)
        if equipo_id:
            ScoutingTarget.objects.filter(pk=target.pk).update(team_id=equipo_id)


def deshacer(apps, schema_editor):
    # Reversible a efectos prácticos: volver a dejarlos sin categoría.
    ScoutingTarget = apps.get_model('football', 'ScoutingTarget')
    ScoutingTarget.objects.update(team=None)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0240_direccion_por_equipo'),
    ]

    operations = [
        migrations.RunPython(asignar_equipo_principal, deshacer),
    ]
