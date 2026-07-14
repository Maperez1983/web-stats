from . import permissions
from .session_task_editor_services import _forbid_if_workspace_module_disabled


def can_access_sessions_workspace(user):
    return permissions.can_access_sessions_workspace(user)


def forbid_if_workspace_module_disabled(request, module_key, label="módulo"):
    return _forbid_if_workspace_module_disabled(request, module_key, label=label)
