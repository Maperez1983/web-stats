from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from . import permissions, workspace_context
from .models import TacticalPlaybookClip

from .views import (
    task_assistant_blueprints_api,
    task_assistant_blueprint_save_api,
    task_assistant_knowledge_api,
    task_assistant_knowledge_upload_api,
    tactical_playbook_clips_api,
    tactical_playbook_clip_save_api,
    tactical_playbook_task_save_api,
    tactical_playbook_clip_delete_api,
    tactical_playbook_clip_favorite_api,
    tactical_playbook_clip_share_create,
    tactical_playbook_clip_clone_api,
    share_tactical_playbook_clip_page,
)


def _forbid_if_tactical_module_disabled(request):
    forbidden = permissions.forbid_if_workspace_module_disabled(request, 'tactics', label='táctica')
    if forbidden:
        fallback = permissions.forbid_if_workspace_module_disabled(request, 'sessions', label='sesiones')
        if fallback:
            return forbidden
    return None


@login_required
def tactical_playbook_teams_api(request):
    """
    Lista equipos accesibles (para clonar clips) dentro del workspace club activo.
    """
    if not permissions.can_access_sessions_workspace(request.user):
        return JsonResponse({'ok': False, 'error': 'No tienes permisos.'}, status=403)
    forbidden = _forbid_if_tactical_module_disabled(request)
    if forbidden:
        return forbidden
    workspace = workspace_context.get_active_workspace(request)
    links = workspace_context.workspace_team_links_for_user(workspace, request.user) if workspace else []
    items = []
    for link in (links or [])[:24]:
        team = getattr(link, 'team', None)
        if not team:
            continue
        items.append({
            'id': int(team.id),
            'slug': str(team.slug or ''),
            'name': str(team.display_name or team.name or ''),
            'is_default': bool(getattr(link, 'is_default', False)),
        })
    return JsonResponse({'ok': True, 'items': items})


@login_required
def tactical_playbook_versions_api(request):
    """
    Lista versiones (v1/v2/...) de un clip (por version_group).
    """
    if not permissions.can_access_sessions_workspace(request.user):
        return JsonResponse({'ok': False, 'error': 'No tienes permisos.'}, status=403)
    forbidden = _forbid_if_tactical_module_disabled(request)
    if forbidden:
        return forbidden
    version_group = str(request.GET.get('version_group') or '').strip()
    if not version_group:
        return JsonResponse({'ok': False, 'error': 'version_group requerido.'}, status=400)
    primary_team = workspace_context.get_active_team_for_request(request)
    if not primary_team:
        primary_team = workspace_context.team_from_request_param(request)
    if not primary_team:
        return JsonResponse({'ok': False, 'error': 'Equipo principal no configurado.'}, status=400)
    try:
        qs = TacticalPlaybookClip.objects.filter(team=primary_team, version_group=version_group).order_by('-version_number', '-updated_at', '-id')
    except Exception:
        qs = TacticalPlaybookClip.objects.none()
    payload = []
    for obj in list(qs[:24]):
        payload.append({
            'id': int(obj.id),
            'name': str(obj.name or '').strip(),
            'folder': str(obj.folder or '').strip(),
            'tags': obj.tags if isinstance(obj.tags, list) else [],
            'steps': obj.steps if isinstance(obj.steps, list) else [],
            'created_by': str(obj.created_by or '').strip(),
            'created_at': obj.created_at.isoformat() if getattr(obj, 'created_at', None) else None,
            'updated_at': obj.updated_at.isoformat() if getattr(obj, 'updated_at', None) else None,
            'version_group': str(getattr(obj, 'version_group', '') or ''),
            'version_number': int(getattr(obj, 'version_number', 1) or 1),
            'is_latest': bool(getattr(obj, 'is_latest', True)),
        })
    return JsonResponse({'ok': True, 'items': payload})
