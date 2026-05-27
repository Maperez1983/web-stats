from django.urls import reverse

from . import permissions, workspace_context
from .models import Workspace


def build_active_workspace_badge(request):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        return None
    subtitle = ''
    if workspace.kind == Workspace.KIND_CLUB:
        active_team = workspace_context.get_active_team_for_request(request)
        if active_team:
            subtitle = active_team.display_name or active_team.name
        elif workspace.primary_team_id:
            subtitle = workspace.primary_team.display_name or workspace.primary_team.name
    elif workspace.kind == Workspace.KIND_TASK_STUDIO and workspace.owner_user_id:
        subtitle = workspace.owner_user.get_username()
    return {
        'id': workspace.id,
        'name': workspace.name,
        'kind': workspace.kind,
        'kind_label': workspace.get_kind_display(),
        'subtitle': subtitle,
    }


def workspace_entry_url(workspace, *, user=None):
    if not workspace:
        return reverse('platform-overview')
    if workspace.kind == Workspace.KIND_TASK_STUDIO:
        return reverse('platform-overview')
    candidates = [
        ('dashboard', reverse('dashboard-home')),
        ('coach_overview', reverse('coach-detail')),
        ('players', reverse('player-dashboard')),
        ('convocation', reverse('convocation')),
        ('match_actions', reverse('match-action-page')),
        ('sessions', reverse('sessions')),
        ('analysis', reverse('analysis')),
        ('abp_board', reverse('coach-abp-board')),
        ('manual_stats', reverse('manual-player-stats')),
    ]
    for module_key, url in candidates:
        if permissions.workspace_has_module_for_user(workspace, module_key, user=user):
            return url
    return reverse('platform-workspace-detail', args=[workspace.id])
