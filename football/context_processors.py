from __future__ import annotations

import os


def build_meta(request):
    """
    Metadatos para cache-busting de estáticos.

    Render suele exponer `RENDER_GIT_COMMIT` (o variables similares). Si no existe,
    devolvemos vacío para no añadir querystrings.
    """
    build_id = (
        os.getenv('RENDER_GIT_COMMIT')
        or os.getenv('RENDER_DEPLOY_ID')
        or os.getenv('SOURCE_VERSION')
        or os.getenv('GIT_SHA')
        or ''
    ).strip()
    return {
        'static_build_id': build_id,
    }


def workspace_access(request):
    """
    Contexto global para plantillas:
    - workspace activo
    - URL de entrada (primer módulo permitido)
    - flags de acceso por módulo (según módulos activos + permisos del miembro)
    """
    try:
        # Import perezoso para evitar dependencias circulares en import-time.
        from football.views import (  # noqa: WPS433 (lazy import)
            _get_active_workspace,
            _get_active_team_for_request,
            _workspace_team_links,
            _build_active_workspace_badge,
            _workspace_entry_url,
            _workspace_default_modules,
            _workspace_has_module_for_user,
            _can_manage_workspace,
            _is_admin_user,
        )
        from football.models import Workspace  # noqa: WPS433 (lazy import)
    except Exception:
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = _get_active_workspace(request)
    active_team = _get_active_team_for_request(request)
    badge = _build_active_workspace_badge(request)
    entry_url = _workspace_entry_url(workspace, user=request.user) if workspace else ''
    can_manage = False
    is_admin = False
    try:
        can_manage = bool(_can_manage_workspace(request.user, workspace)) if workspace else False
        is_admin = bool(_is_admin_user(request.user))
    except Exception:
        can_manage = False
        is_admin = False

    module_access = {}
    try:
        kind = workspace.kind if workspace else Workspace.KIND_CLUB
        defaults = _workspace_default_modules(kind)
        for key in defaults.keys():
            module_access[key] = bool(_workspace_has_module_for_user(workspace, key, user=request.user)) if workspace else True
    except Exception:
        module_access = {}

    team_options = []
    try:
        if workspace and workspace.kind == Workspace.KIND_CLUB:
            links = _workspace_team_links(workspace)
            for link in links:
                team = getattr(link, 'team', None)
                if not team:
                    continue
                category = str(getattr(team, 'category', '') or '').strip()
                name = str(getattr(team, 'display_name', '') or getattr(team, 'name', '') or '').strip()
                label = f'{category} · {name}' if category else name
                team_options.append(
                    {
                        'id': int(team.id),
                        'label': label,
                        'category': category,
                        'name': name,
                        'game_format': str(getattr(team, 'game_format', '') or '').strip(),
                        'game_format_label': str(getattr(team, 'get_game_format_display', lambda: '')() or '').strip(),
                        'is_default': bool(getattr(link, 'is_default', False)),
                    }
                )
    except Exception:
        team_options = []

    return {
        'active_workspace': badge,
        'workspace_entry_url': entry_url,
        'workspace_module_access': module_access,
        'active_team': active_team,
        'active_team_options': team_options,
        'active_team_current_path': request.get_full_path() if request else '',
        'can_manage_workspace': can_manage,
        'is_admin_user': is_admin,
    }
