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
            _build_active_workspace_badge,
            _workspace_entry_url,
            _workspace_default_modules,
            _workspace_has_module_for_user,
        )
        from football.models import Workspace  # noqa: WPS433 (lazy import)
    except Exception:
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = _get_active_workspace(request)
    badge = _build_active_workspace_badge(request)
    entry_url = _workspace_entry_url(workspace, user=request.user) if workspace else ''

    module_access = {}
    try:
        kind = workspace.kind if workspace else Workspace.KIND_CLUB
        defaults = _workspace_default_modules(kind)
        for key in defaults.keys():
            module_access[key] = bool(_workspace_has_module_for_user(workspace, key, user=request.user)) if workspace else True
    except Exception:
        module_access = {}

    return {
        'active_workspace': badge,
        'workspace_entry_url': entry_url,
        'workspace_module_access': module_access,
    }
