from django.http import HttpResponse

from .models import AppUserRole, Workspace, WorkspaceMembership
from . import workspace_context


TECHNICAL_ROLES = {
    AppUserRole.ROLE_COACH,
    AppUserRole.ROLE_FITNESS,
    AppUserRole.ROLE_GOALKEEPER,
    AppUserRole.ROLE_ANALYST,
    AppUserRole.ROLE_ADMIN,
}


def has_club_workspace_access(user):
    if not user or not user.is_authenticated:
        return False
    if workspace_context.get_user_role(user) == AppUserRole.ROLE_PLAYER:
        return False
    return (
        WorkspaceMembership.objects.filter(user=user, workspace__kind=Workspace.KIND_CLUB, workspace__is_active=True).exists()
        or Workspace.objects.filter(owner_user=user, kind=Workspace.KIND_CLUB, is_active=True).exists()
    )


def can_edit_match_actions(user):
    if not user or not user.is_authenticated:
        return False
    if workspace_context.is_admin_user(user):
        return True
    return workspace_context.get_user_role(user) in TECHNICAL_ROLES or has_club_workspace_access(user)


def can_access_sessions_workspace(user):
    role = workspace_context.get_user_role(user)
    if not user or not user.is_authenticated:
        return False
    if workspace_context.is_admin_user(user):
        return True
    return role in TECHNICAL_ROLES or has_club_workspace_access(user)


def can_access_coach_workspace(user):
    if not user or not user.is_authenticated:
        return False
    if workspace_context.is_admin_user(user):
        return True
    return workspace_context.get_user_role(user) in TECHNICAL_ROLES or has_club_workspace_access(user)


def workspace_has_module_for_user(workspace, module_key, *, user=None):
    if not workspace or not module_key:
        return False
    if getattr(workspace, 'kind', None) == Workspace.KIND_TASK_STUDIO:
        return True
    modules = getattr(workspace, 'enabled_modules', None)
    if not isinstance(modules, dict):
        return True
    return bool(modules.get(str(module_key), False))


def forbid_if_workspace_module_disabled(request, module_key, label='modulo'):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        return None
    if workspace_has_module_for_user(workspace, module_key, user=getattr(request, 'user', None)):
        return None
    return HttpResponse(f'Este club no tiene activo el modulo {label}.', status=403)
