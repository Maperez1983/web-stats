import logging
import os

from django.http import HttpResponse

from .models import AppUserRole, Workspace, WorkspaceMembership
from . import workspace_context


logger = logging.getLogger(__name__)


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
        return True
    if getattr(workspace, 'kind', None) == Workspace.KIND_TASK_STUDIO:
        return True
    raw = getattr(workspace, 'enabled_modules', None)
    defaults = workspace_default_modules(getattr(workspace, 'kind', Workspace.KIND_CLUB))
    modules = dict(defaults)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in defaults or str(key).startswith('deliverable__') or str(key).startswith('module__'):
                modules[key] = bool(value)
        try:
            has_module_flags = any(str(k).startswith('module__') for k in raw.keys())
            if has_module_flags and 'module__tactics' not in raw and modules.get('tactics') is False:
                modules['tactics'] = bool(defaults.get('tactics', False))
        except Exception:
            logger.debug(
                'No se pudo normalizar los flags de modulos del workspace %s',
                getattr(workspace, 'id', None),
                exc_info=True,
            )
    if user is not None and not workspace_member_allows_module(workspace, user, module_key):
        return False
    return bool(modules.get(str(module_key), False))


def workspace_default_modules(kind):
    if kind == Workspace.KIND_TASK_STUDIO:
        return {
            'task_studio_home': True,
            'task_studio_profile': True,
            'task_studio_roster': True,
            'task_studio_tasks': True,
            'task_studio_pdfs': True,
        }
    academy_default = str(os.environ.get('ACADEMY_DEFAULT_ENABLED', '') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    return {
        'dashboard': True,
        'coach_overview': True,
        'players': True,
        'convocation': True,
        'match_actions': True,
        'sessions': True,
        'academy': academy_default,
        'analysis': True,
        'abp_board': True,
        'tactics': True,
        'manual_stats': True,
    }


def workspace_member_allows_module(workspace, user, module_key):
    if not workspace or not module_key:
        return True
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if workspace_context.can_access_platform(user):
        return True
    membership = workspace_context.workspace_membership_for_user(workspace, user)
    if not membership:
        if int(getattr(workspace, 'owner_user_id', 0) or 0) == int(getattr(user, 'id', 0) or 0):
            return True
        return False
    if membership.role in {WorkspaceMembership.ROLE_OWNER, WorkspaceMembership.ROLE_ADMIN}:
        return True
    raw = getattr(membership, 'module_access', None)
    if not isinstance(raw, dict) or not raw:
        return True
    return raw.get(module_key, True) is not False


def forbid_if_workspace_module_disabled(request, module_key, label='modulo'):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        return None
    if workspace_has_module_for_user(workspace, module_key, user=getattr(request, 'user', None)):
        return None
    return HttpResponse(f'Este club no tiene activo el modulo {label}.', status=403)
