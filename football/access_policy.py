from .models import WorkspaceMembership


MANAGE_WORKSPACE_ROLES = {
    WorkspaceMembership.ROLE_OWNER,
    WorkspaceMembership.ROLE_ADMIN,
}


def workspace_membership_for_user(workspace, user):
    if not workspace or not user or not getattr(user, 'is_authenticated', False):
        return None
    return WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()


def is_workspace_owner_user(user, workspace):
    if not workspace or not user or not getattr(user, 'is_authenticated', False):
        return False
    try:
        return int(getattr(workspace, 'owner_user_id', 0) or 0) == int(getattr(user, 'id', 0) or 0)
    except Exception:
        return False


def can_view_workspace(user, workspace, *, platform_access=False):
    if platform_access:
        return True
    if is_workspace_owner_user(user, workspace):
        return True
    return bool(workspace_membership_for_user(workspace, user))


def can_manage_workspace(user, workspace, *, platform_access=False):
    if platform_access:
        return True
    if is_workspace_owner_user(user, workspace):
        return True
    membership = workspace_membership_for_user(workspace, user)
    return bool(membership and membership.role in MANAGE_WORKSPACE_ROLES)
