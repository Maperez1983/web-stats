from . import permissions


def can_access_sessions_workspace(user):
    return permissions.can_access_sessions_workspace(user)


def forbid_if_workspace_module_disabled(request, module_key, label='módulo'):
    from .views import _forbid_if_workspace_module_disabled

    return _forbid_if_workspace_module_disabled(request, module_key, label=label)
