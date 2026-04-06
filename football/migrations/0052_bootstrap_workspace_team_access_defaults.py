from django.conf import settings
from django.db import migrations


def bootstrap_team_access(apps, schema_editor):
    Workspace = apps.get_model('football', 'Workspace')
    WorkspaceTeam = apps.get_model('football', 'WorkspaceTeam')
    WorkspaceMembership = apps.get_model('football', 'WorkspaceMembership')
    WorkspaceTeamAccess = apps.get_model('football', 'WorkspaceTeamAccess')

    club_kind = getattr(Workspace, 'KIND_CLUB', 'club')
    role_owner = getattr(WorkspaceMembership, 'ROLE_OWNER', 'owner')
    role_admin = getattr(WorkspaceMembership, 'ROLE_ADMIN', 'admin')

    club_workspaces = list(Workspace.objects.filter(kind=club_kind, is_active=True).order_by('id'))
    for workspace in club_workspaces:
        links = list(WorkspaceTeam.objects.filter(workspace=workspace).order_by('-is_default', 'id'))
        if not links:
            continue
        default_link = next((l for l in links if getattr(l, 'is_default', False)), None) or links[0]
        default_team_id = getattr(default_link, 'team_id', None)
        if not default_team_id:
            continue

        memberships = list(WorkspaceMembership.objects.filter(workspace=workspace).order_by('id'))
        for membership in memberships:
            # Owners/admins gestionan: no les forzamos acceso por categoría.
            if getattr(membership, 'role', None) in {role_owner, role_admin}:
                continue
            # Si ya tiene algún acceso explícito, no tocamos nada.
            if WorkspaceTeamAccess.objects.filter(workspace=workspace, user_id=membership.user_id).exists():
                continue
            WorkspaceTeamAccess.objects.get_or_create(
                workspace=workspace,
                team_id=default_team_id,
                user_id=membership.user_id,
                defaults={'is_default': True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ('football', '0051_workspace_team_access'),
    ]

    operations = [
        migrations.RunPython(bootstrap_team_access, migrations.RunPython.noop),
    ]

