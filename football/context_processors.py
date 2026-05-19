from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from django.core.cache import cache


@lru_cache(maxsize=1)
def _static_build_id() -> str:
    """
    Cache-busting para estáticos.

    Render suele exponer `RENDER_GIT_COMMIT` (o variables similares). Si no existe,
    usamos un fallback local (mtimes de assets core) para evitar que Safari/iPad
    se quede enganchado a un JS antiguo cuando cambiamos otras pantallas.
    """
    build_id = (
        os.getenv('RENDER_GIT_COMMIT')
        or os.getenv('RENDER_DEPLOY_ID')
        or os.getenv('SOURCE_VERSION')
        or os.getenv('GIT_SHA')
        or ''
    ).strip()
    if build_id:
        return build_id
    try:
        base_dir = Path(__file__).resolve().parent.parent
        candidates = [
            base_dir / 'football' / 'static' / 'football' / 'js' / 'sessions_tactical_pad.js',
            base_dir / 'football' / 'static' / 'football' / 'js' / 'match_actions_page.js',
            base_dir / 'football' / 'static' / 'football' / 'js' / 'analysis_video_studio.js',
            base_dir / 'football' / 'static' / 'football' / 'js' / 'analysis_video_studio_simple_ui.js',
            base_dir / 'static' / 'football' / 'css' / 'product_system.css',
            base_dir / 'static' / 'football' / 'css' / 'commercial.css',
        ]
        mtimes = []
        for path in candidates:
            try:
                if path.exists():
                    mtimes.append(int(path.stat().st_mtime))
            except Exception:
                continue
        if mtimes:
            return str(max(mtimes))
    except Exception:
        return ''
    return ''


def build_meta(request):
    """
    Metadatos para cache-busting de estáticos.
    """
    return {
        'static_build_id': _static_build_id(),
    }


def brand_theme(request):
    """
    Paleta corporativa por equipo (sin romper nada):
    - Fuente: WorkspacePreference key `brand_theme:v1`
    - Se aplica como CSS variables `--prod-*` (fallback seguro a defaults).

    Schema esperado:
    {
      "default": {
        "primary":"#2f7d32",
        "secondary":"#f4b400",
        "bg":"#08111d",
        "text":"#f5f7fa",
        "ui":"dark|light|hc",
        "bg_light":"#f4f7fb",
        "text_light":"#0f172a"
      },
      "teams": {
        "<team_id>": {
          "primary":"#...",
          "secondary":"#...",
          "ui":"dark|light|hc",
          "bg_light":"#...",
          "text_light":"#..."
        }
      }
    }
    """
    try:
        from football.views import _get_active_workspace, _get_active_team_for_request  # noqa: WPS433 (lazy import)
        from football.models import WorkspacePreference  # noqa: WPS433 (lazy import)
    except Exception:
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = None
    team = None
    try:
        workspace = _get_active_workspace(request)
    except Exception:
        workspace = None
    try:
        team = _get_active_team_for_request(request)
    except Exception:
        team = None
    if not workspace:
        return {}

    cache_ttl_s = 60
    try:
        cache_ttl_s = max(5, int(os.getenv('PERF_CONTEXT_CACHE_SECONDS') or 60))
    except Exception:
        cache_ttl_s = 60

    team_id = int(getattr(team, 'id', 0) or 0) if team else 0
    raw = None
    cache_key = f'ctx:brand_theme:v1:w{int(workspace.id)}:t{team_id}'
    try:
        raw = cache.get(cache_key)
    except Exception:
        raw = None
    if raw is None:
        pref = None
        try:
            pref = WorkspacePreference.objects.filter(workspace=workspace, key='brand_theme:v1').only('id', 'value').first()
        except Exception:
            pref = None
        raw = pref.value if pref and isinstance(pref.value, dict) else {}
        try:
            cache.set(cache_key, raw, cache_ttl_s)
        except Exception:
            pass
    default = raw.get('default') if isinstance(raw.get('default'), dict) else {}
    teams = raw.get('teams') if isinstance(raw.get('teams'), dict) else {}
    team_key = str(team_id or '').strip()
    override = teams.get(team_key) if team_key and isinstance(teams.get(team_key), dict) else {}

    def _color(value: str, fallback: str) -> str:
        text = str(value or '').strip()
        if not text:
            return fallback
        # Basic guardrail: allow #RGB/#RRGGBB and rgba()/rgb().
        if text.startswith('#') and len(text) in {4, 7, 9}:
            return text
        if text.lower().startswith('rgb'):
            return text
        return fallback

    theme = {
        'primary': _color(override.get('primary') or default.get('primary'), '#2f7d32'),
        'secondary': _color(override.get('secondary') or default.get('secondary'), '#f4b400'),
        'bg': _color(override.get('bg') or default.get('bg'), '#08111d'),
        'text': _color(override.get('text') or default.get('text'), '#f5f7fa'),
        'muted': _color(override.get('muted') or default.get('muted'), 'rgba(226, 232, 240, 0.74)'),
        'line': _color(override.get('line') or default.get('line'), 'rgba(144, 161, 185, 0.22)'),
        'panel_flat': _color(override.get('panel_flat') or default.get('panel_flat'), 'rgba(14, 23, 39, 0.96)'),
        'info': _color(override.get('info') or default.get('info'), '#22d3ee'),
        # Default del producto: claro (estilo informe) salvo que el club/equipo fuerce otro.
        'ui': str(override.get('ui') or default.get('ui') or 'light').strip().lower(),
        'bg_light': _color(override.get('bg_light') or default.get('bg_light'), '#f4f7fb'),
        'text_light': _color(override.get('text_light') or default.get('text_light'), '#0f172a'),
    }
    if theme['ui'] not in {'dark', 'light', 'hc'}:
        theme['ui'] = 'dark'

    css_vars = {
        '--prod-primary': theme['primary'],
        '--prod-secondary': theme['secondary'],
        '--prod-bg': theme['bg'],
        '--prod-text': theme['text'],
        '--prod-muted': theme['muted'],
        '--prod-line': theme['line'],
        '--prod-panel-flat': theme['panel_flat'],
        '--prod-info': theme['info'],
    }
    css_vars_light = {
        '--prod-bg': theme['bg_light'],
        '--prod-text': theme['text_light'],
        # En tema claro, el muted debe oscurecerse para ser legible.
        '--prod-muted': 'rgba(15, 23, 42, 0.72)',
        '--prod-muted-soft': 'rgba(15, 23, 42, 0.82)',
        '--prod-line': 'rgba(15, 23, 42, 0.14)',
        '--prod-panel-flat': 'rgba(255, 255, 255, 0.92)',
    }
    return {
        'brand_theme': {
            **theme,
            'css_vars': css_vars,
            'css_vars_light': css_vars_light,
            'team_id': int(getattr(team, 'id', 0) or 0) if team else None,
            'workspace_id': int(getattr(workspace, 'id', 0) or 0),
        }
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
            _workspace_team_links_for_user,
            _build_active_workspace_badge,
            _workspace_entry_url,
            _workspace_default_modules,
            _workspace_has_module_for_user,
            _can_access_platform,
            _available_workspaces_for_user,
            _can_manage_workspace,
            _is_admin_user,
        )
        from football.models import Workspace, WorkspaceMembership  # noqa: WPS433 (lazy import)
    except Exception:
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = _get_active_workspace(request)
    # Platform admins: si no hay workspace activo (por diseño), pero el sistema solo tiene
    # un cliente club, lo fijamos para que la navegación (Admin/Categorías) sea consistente.
    if not workspace:
        try:
            is_admin_user = bool(_is_admin_user(request.user))
        except Exception:
            is_admin_user = False
        if is_admin_user:
            try:
                club_ws = list(
                    Workspace.objects
                    .filter(kind=Workspace.KIND_CLUB, is_active=True)
                    .order_by('id')[:2]
                )
                if len(club_ws) == 1:
                    workspace = club_ws[0]
                    if request and hasattr(request, 'session'):
                        request.session['active_workspace_id'] = workspace.id
            except Exception:
                pass
    active_team = _get_active_team_for_request(request)
    active_team_query = ''
    try:
        if active_team and getattr(active_team, 'id', None):
            active_team_query = f'?team={int(active_team.id)}'
    except Exception:
        active_team_query = ''
    badge = _build_active_workspace_badge(request)
    entry_url = _workspace_entry_url(workspace, user=request.user) if workspace else ''
    try:
        from django.urls import reverse  # noqa: WPS433 (lazy import)
        club_dashboard_url = reverse('dashboard-home')
        if _can_access_platform(request.user):
            club_dashboard_url = f'{club_dashboard_url}?home=club'
    except Exception:
        club_dashboard_url = ''
    can_manage = False
    is_admin = False
    can_access_staff = False
    try:
        can_manage = bool(_can_manage_workspace(request.user, workspace)) if workspace else False
        is_admin = bool(_is_admin_user(request.user))
        # Staff (cuerpo técnico) debe ser accesible para perfiles técnicos aunque el workspace o el menú varíen.
        # Usamos la misma lógica que el backend para permitir/denegar el acceso.
        from football.views import _can_access_coach_workspace  # noqa: WPS433 (lazy import)

        can_access_staff = bool(_can_access_coach_workspace(request.user))
    except Exception:
        can_manage = False
        is_admin = False
        can_access_staff = False

    team_switcher_enabled = False
    try:
        raw_flag = str(os.getenv('ENABLE_TEAM_SWITCHER', '') or '').strip().lower()
        # Compatibilidad: si se define explícitamente, respeta el flag.
        # Si NO se define, habilitamos el selector cuando el usuario tiene acceso a >1 equipo/categoría
        # para evitar confusiones (p.ej. iPad/app nueva sesión cayendo al Senior).
        team_switcher_enabled = raw_flag in {'1', 'true', 'yes', 'on'}
    except Exception:
        team_switcher_enabled = False

    cache_ttl_s = 45
    try:
        cache_ttl_s = max(5, int(os.getenv('PERF_CONTEXT_CACHE_SECONDS') or 45))
    except Exception:
        cache_ttl_s = 45

    ctx_cache_key = ''
    if workspace:
        try:
            ctx_cache_key = f'ctx:workspace_access:v1:w{int(workspace.id)}:u{int(request.user.id)}'
        except Exception:
            ctx_cache_key = ''

    cached_payload = None
    if ctx_cache_key:
        try:
            cached_payload = cache.get(ctx_cache_key)
        except Exception:
            cached_payload = None
    if isinstance(cached_payload, dict) and cached_payload:
        cached_payload = dict(cached_payload)
        cached_payload['active_team_current_path'] = request.get_full_path() if request else ''
        return cached_payload

    module_access = {}
    try:
        kind = workspace.kind if workspace else Workspace.KIND_CLUB
        defaults = _workspace_default_modules(kind)
        enabled_modules = getattr(workspace, 'enabled_modules', None)
        enabled_modules = enabled_modules if isinstance(enabled_modules, dict) else {}

        membership = None
        try:
            membership = (
                WorkspaceMembership.objects
                .filter(workspace=workspace, user=request.user)
                .only('id', 'role', 'module_access')
                .first()
            )
        except Exception:
            membership = None

        user_is_platform = False
        user_is_owner = False
        try:
            user_is_platform = bool(_can_access_platform(request.user))
        except Exception:
            user_is_platform = False
        try:
            user_is_owner = bool(int(getattr(workspace, 'owner_user_id', 0) or 0) == int(getattr(request.user, 'id', 0) or 0))
        except Exception:
            user_is_owner = False

        member_role = str(getattr(membership, 'role', '') or '').strip()
        member_module_access = getattr(membership, 'module_access', None)
        member_module_access = member_module_access if isinstance(member_module_access, dict) else {}

        def _enabled_for_workspace(key: str) -> bool:
            if key in defaults or str(key).startswith('deliverable__') or str(key).startswith('module__'):
                if key in enabled_modules:
                    return bool(enabled_modules.get(key))
            return bool(defaults.get(key, False))

        def _member_allows(key: str) -> bool:
            if user_is_platform or user_is_owner:
                return True
            if not membership:
                return False
            if member_role in {WorkspaceMembership.ROLE_OWNER, WorkspaceMembership.ROLE_ADMIN}:
                return True
            if not member_module_access:
                return True
            return member_module_access.get(key, True) is not False

        for key in defaults.keys():
            module_access[key] = bool(_enabled_for_workspace(key) and _member_allows(key))
    except Exception:
        module_access = {}

    team_options = []
    try:
        if workspace and workspace.kind == Workspace.KIND_CLUB:
            links = _workspace_team_links_for_user(workspace, request.user)
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
            if raw_flag == '' and len(team_options) > 1:
                # Sin flag explícito, habilitar por presencia de múltiples categorías.
                team_switcher_enabled = True
    except Exception:
        team_options = []

    workspace_options = []
    try:
        ws_cache_key = f'ctx:workspace_options:v1:u{int(request.user.id)}'
        cached_ws = None
        try:
            cached_ws = cache.get(ws_cache_key)
        except Exception:
            cached_ws = None
        if isinstance(cached_ws, list):
            workspace_options = cached_ws
        else:
            candidates = list(
                _available_workspaces_for_user(request.user)
                .only('id', 'name', 'kind')
                .order_by('kind', 'name', 'id')[:12]
            )
            for ws in candidates:
                workspace_options.append(
                    {
                        'id': int(ws.id),
                        'label': str(getattr(ws, 'name', '') or f'Workspace {ws.id}').strip(),
                        'kind': str(getattr(ws, 'kind', '') or '').strip(),
                        'kind_label': str(getattr(ws, 'get_kind_display', lambda: '')() or '').strip(),
                    }
                )
            try:
                cache.set(ws_cache_key, workspace_options, cache_ttl_s)
            except Exception:
                pass
    except Exception:
        workspace_options = []

    payload = {
        'active_workspace': badge,
        'workspace_entry_url': entry_url,
        'club_dashboard_url': club_dashboard_url,
        'workspace_module_access': module_access,
        'active_team': active_team,
        'active_team_query': active_team_query,
        'active_team_options': team_options,
        'team_switcher_enabled': bool(team_switcher_enabled),
        'active_workspace_options': workspace_options,
        'active_team_current_path': request.get_full_path() if request else '',
        'can_manage_workspace': can_manage,
        'is_admin_user': is_admin,
        'can_access_staff': can_access_staff,
    }
    if ctx_cache_key:
        try:
            to_cache = dict(payload)
            to_cache.pop('active_team_current_path', None)
            cache.set(ctx_cache_key, to_cache, cache_ttl_s)
        except Exception:
            pass
    return payload
