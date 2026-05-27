import json
import re

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .api_utils import api_error, api_ok
from .models import Workspace, WorkspacePreference
from .services import _parse_int
from . import workspace_context


@login_required
@require_POST
def workspace_set_active_team(request):
    """
    Cambia el equipo/categoría activo del workspace club (persistido en sesión).

    Importante:
    - No modifica `workspace.primary_team` (equipo "principal" legacy del cliente).
    - Valida que el equipo pertenezca al workspace mediante WorkspaceTeam.
    """
    workspace = workspace_context.get_active_workspace(request)
    next_url = (request.POST.get('next') or '').strip() or request.META.get('HTTP_REFERER') or reverse('dashboard-home')
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return redirect(next_url)

    team_id = _parse_int(request.POST.get('team_id') or request.POST.get('team') or request.POST.get('active_team_id'))
    if not team_id:
        return redirect(next_url)

    links = workspace_context.workspace_team_links_for_user(workspace, request.user)
    allowed_team_ids = {int(link.team_id) for link in links if getattr(link, 'team_id', None)}
    if int(team_id) not in allowed_team_ids:
        return redirect(next_url)

    mapping = request.session.get('active_team_by_workspace')
    if not isinstance(mapping, dict):
        mapping = {}
    mapping[str(workspace.id)] = int(team_id)
    request.session['active_team_by_workspace'] = mapping
    return redirect(next_url)


@login_required
@require_POST
def workspace_set_active_workspace(request):
    """
    Fija el workspace activo en sesión para usuarios no-Platform (y también Platform).
    Esto evita mezclar datos (p.ej. caer al equipo global Benagalbón cuando no hay contexto).
    """
    desired_id = _parse_int(request.POST.get('workspace_id') or request.POST.get('workspace') or 0)
    next_url = (request.POST.get('next') or '').strip() or request.META.get('HTTP_REFERER') or reverse('dashboard-home')
    if not desired_id:
        return redirect(next_url)
    available = workspace_context.available_workspaces_for_user(request.user)
    workspace = available.filter(id=desired_id, is_active=True).first()
    if not workspace:
        return redirect(next_url)
    request.session['active_workspace_id'] = workspace.id
    return redirect(next_url)


def _workspace_pref_key(raw_key: str) -> str:
    key = str(raw_key or '').strip()
    key = re.sub(r'[^a-zA-Z0-9_\-:\.]+', '', key)
    return key[:80]


@login_required
def workspace_preference_get_api(request):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        return api_error('Workspace no configurado.', status=400, code='workspace_missing')
    if not workspace_context.can_view_workspace(request.user, workspace) and not workspace_context.can_access_platform(request.user):
        return api_error('No autorizado.', status=403, code='forbidden')
    key = _workspace_pref_key(request.GET.get('key') or '')
    if not key:
        return api_error('key requerido.', status=400, code='key_required')
    pref = WorkspacePreference.objects.filter(workspace=workspace, key=key).first()
    return api_ok({'key': key, 'value': pref.value if pref else None, 'updated_at': pref.updated_at if pref else None})


@login_required
@require_POST
def workspace_preference_set_api(request):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        return api_error('Workspace no configurado.', status=400, code='workspace_missing')
    if not workspace_context.can_view_workspace(request.user, workspace) and not workspace_context.can_access_platform(request.user):
        return api_error('No autorizado.', status=403, code='forbidden')
    try:
        data = json.loads((request.body or b'{}').decode('utf-8') or '{}')
    except Exception:
        data = {}
    key = _workspace_pref_key(data.get('key') or '')
    if not key:
        return api_error('key requerido.', status=400, code='key_required')
    value = data.get('value')
    if value is None:
        value = {}
    try:
        raw_size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
    except Exception:
        raw_size = 0
    if raw_size > 150_000:
        return api_error('Preferencia demasiado grande.', status=400, code='payload_too_large')
    obj, _ = WorkspacePreference.objects.update_or_create(
        workspace=workspace,
        key=key,
        defaults={'value': value},
    )
    return api_ok({'key': key, 'updated_at': obj.updated_at})


@login_required
@require_POST
def workspace_sync_competition_api(request):
    """
    Sincroniza el contexto competitivo del workspace club actual (owner/admin).
    Útil para onboarding/autoservicio sin depender de Platform.
    """
    workspace = workspace_context.get_active_workspace(request)
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return JsonResponse({'status': 'error', 'message': 'No hay workspace club activo.'}, status=400)
    if not workspace_context.can_manage_workspace(request.user, workspace):
        return JsonResponse({'status': 'error', 'message': 'No autorizado.'}, status=403)
    primary_team = workspace_context.get_active_team_for_request(request) or getattr(workspace, 'primary_team', None)
    if not primary_team:
        return JsonResponse({'status': 'error', 'message': 'No hay equipo configurado.'}, status=400)

    lock_key = f'workspace_sync_lock:{workspace.id}:{primary_team.id}'
    if not cache.add(lock_key, '1', timeout=180):
        return JsonResponse({'status': 'error', 'message': 'Ya hay una sincronización en curso.'}, status=429)
    try:
        from . import views as core_views
        context, sync_error = core_views._sync_workspace_competition_context(workspace, primary_team=primary_team)
        if sync_error:
            return JsonResponse({'status': 'error', 'message': sync_error}, status=500)
        return JsonResponse(
            {
                'status': 'success',
                'message': 'Sincronización completada.',
                'sync_status': str(getattr(context, 'sync_status', '') or '').strip(),
                'last_sync_at': getattr(context, 'last_sync_at', None).isoformat() if getattr(context, 'last_sync_at', None) else '',
            }
        )
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc) or 'No se pudo sincronizar.'}, status=500)
    finally:
        cache.delete(lock_key)
