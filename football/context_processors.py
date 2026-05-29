from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from django.core.cache import cache
from django.urls import reverse

from . import permissions, workspace_context, workspace_ui


logger = logging.getLogger(__name__)


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
                logger.debug('No se pudo leer mtime para el asset estatico %s', path, exc_info=True)
                continue
        if mtimes:
            return str(max(mtimes))
    except Exception:
        logger.debug('No se pudo calcular static_build_id local', exc_info=True)
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
        "button_text":"#f5f7fa",
        "button_bg":"#0f172a",
        "panel_flat":"#0e1727",
        "line":"rgba(144, 161, 185, 0.22)",
        "shadow":"medium",
        "system_image_mode":"home|system|both|none",
        "font":"plex|system|avenir|segoe|roboto|georgia|condensed",
        "font_weight":"regular|medium|semibold|bold",
        "font_style":"normal|italic",
        "font_decoration":"none|underline",
        "font_size":"compact|normal|large",
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
        from football.models import WorkspacePreference  # noqa: WPS433 (lazy import)
    except Exception:
        logger.debug('No se pudo cargar WorkspacePreference para brand_theme', exc_info=True)
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = None
    team = None
    try:
        workspace = workspace_context.get_active_workspace(request)
    except Exception:
        logger.debug('No se pudo resolver workspace activo para brand_theme', exc_info=True)
        workspace = None
    try:
        team = workspace_context.get_active_team_for_request(request)
    except Exception:
        logger.debug('No se pudo resolver equipo activo para brand_theme', exc_info=True)
        team = None
    if not workspace:
        return {}

    cache_ttl_s = 60
    try:
        cache_ttl_s = max(5, int(os.getenv('PERF_CONTEXT_CACHE_SECONDS') or 60))
    except Exception:
        logger.debug('PERF_CONTEXT_CACHE_SECONDS invalido; usando TTL por defecto', exc_info=True)
        cache_ttl_s = 60

    team_id = int(getattr(team, 'id', 0) or 0) if team else 0
    raw = None
    cache_key = f'ctx:brand_theme:v1:w{int(workspace.id)}:t{team_id}'
    try:
        raw = cache.get(cache_key)
    except Exception:
        logger.debug('No se pudo leer brand_theme de cache %s', cache_key, exc_info=True)
        raw = None
    if raw is None:
        pref = None
        try:
            pref = WorkspacePreference.objects.filter(workspace=workspace, key='brand_theme:v1').only('id', 'value').first()
        except Exception:
            logger.debug('No se pudo leer brand_theme del workspace %s', getattr(workspace, 'id', None), exc_info=True)
            pref = None
        raw = pref.value if pref and isinstance(pref.value, dict) else {}
        try:
            cache.set(cache_key, raw, cache_ttl_s)
        except Exception:
            logger.debug('No se pudo guardar brand_theme en cache %s', cache_key, exc_info=True)
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
        'button_text': _color(override.get('button_text') or default.get('button_text'), '#f5f7fa'),
        'button_bg': _color(override.get('button_bg') or default.get('button_bg'), 'rgba(15, 23, 42, 0.62)'),
        'muted': _color(override.get('muted') or default.get('muted'), 'rgba(226, 232, 240, 0.74)'),
        'line': _color(override.get('line') or default.get('line'), 'rgba(144, 161, 185, 0.22)'),
        'panel_flat': _color(override.get('panel_flat') or default.get('panel_flat'), 'rgba(14, 23, 39, 0.96)'),
        'info': _color(override.get('info') or default.get('info'), '#22d3ee'),
        'shadow': str(override.get('shadow') or default.get('shadow') or 'medium').strip().lower(),
        'system_image_mode': str(override.get('system_image_mode') or default.get('system_image_mode') or 'home').strip().lower(),
        'font': str(override.get('font') or default.get('font') or 'plex').strip().lower(),
        'font_weight': str(override.get('font_weight') or default.get('font_weight') or 'medium').strip().lower(),
        'font_style': str(override.get('font_style') or default.get('font_style') or 'normal').strip().lower(),
        'font_decoration': str(override.get('font_decoration') or default.get('font_decoration') or 'none').strip().lower(),
        'font_size': str(override.get('font_size') or default.get('font_size') or 'normal').strip().lower(),
        # Default del producto: oscuro (más consistente con la mayoría de pantallas).
        # El club/equipo puede forzar 'light' o 'hc' vía WorkspacePreference si lo desea.
        'ui': str(override.get('ui') or default.get('ui') or 'dark').strip().lower(),
        'bg_light': _color(override.get('bg_light') or default.get('bg_light'), '#f4f7fb'),
        'text_light': _color(override.get('text_light') or default.get('text_light'), '#0f172a'),
    }
    if theme['ui'] not in {'dark', 'light', 'hc'}:
        theme['ui'] = 'dark'
    if theme['shadow'] not in {'none', 'soft', 'medium', 'strong'}:
        theme['shadow'] = 'medium'
    if theme['system_image_mode'] not in {'home', 'system', 'both', 'none'}:
        theme['system_image_mode'] = 'home'
    font_values = {
        'plex': ('"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif', '"IBM Plex Sans", system-ui, sans-serif'),
        'system': ('system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif', 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'),
        'avenir': ('"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif', '"Avenir Next", Avenir, system-ui, sans-serif'),
        'segoe': ('"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif', '"Segoe UI", system-ui, sans-serif'),
        'roboto': ('Roboto, "Helvetica Neue", Arial, system-ui, sans-serif', 'Roboto, "Helvetica Neue", Arial, sans-serif'),
        'georgia': ('Georgia, "Times New Roman", serif', 'Georgia, "Times New Roman", serif'),
        'condensed': ('"Arial Narrow", "Roboto Condensed", "Helvetica Neue", Arial, sans-serif', '"Arial Narrow", "Roboto Condensed", Arial, sans-serif'),
    }
    if theme['font'] not in font_values:
        theme['font'] = 'plex'
    font_ui, font_display = font_values[theme['font']]
    font_weight_values = {
        'regular': '400',
        'medium': '500',
        'semibold': '650',
        'bold': '800',
    }
    font_size_values = {
        'compact': ('15px', '0.94'),
        'normal': ('16px', '1'),
        'large': ('17px', '1.08'),
    }
    if theme['font_weight'] not in font_weight_values:
        theme['font_weight'] = 'medium'
    if theme['font_style'] not in {'normal', 'italic'}:
        theme['font_style'] = 'normal'
    if theme['font_decoration'] not in {'none', 'underline'}:
        theme['font_decoration'] = 'none'
    if theme['font_size'] not in font_size_values:
        theme['font_size'] = 'normal'
    font_size_base, font_size_scale = font_size_values[theme['font_size']]

    shadow_values = {
        'none': ('none', 'none'),
        'soft': ('0 10px 28px rgba(0, 0, 0, 0.16)', '0 8px 20px rgba(0, 0, 0, 0.12)'),
        'medium': ('0 24px 64px rgba(0, 0, 0, 0.34)', '0 16px 36px rgba(0, 0, 0, 0.24)'),
        'strong': ('0 32px 90px rgba(0, 0, 0, 0.48)', '0 22px 56px rgba(0, 0, 0, 0.34)'),
    }
    shadow_lg, shadow_md = shadow_values.get(theme['shadow'], shadow_values['medium'])

    system_image_value = 'none'
    try:
        if theme['system_image_mode'] in {'system', 'both'} and team and getattr(team, 'cover_image', None):
            updated_at = getattr(team, 'cover_updated_at', None)
            version = str(int(updated_at.timestamp())) if updated_at else '1'
            cover_url = f'{reverse("team-cover-image-file", args=[int(team.id)])}?v={version}&w=1800&h=1200&q=76'
            system_image_value = f'url("{cover_url}")'
    except Exception:
        system_image_value = 'none'

    css_vars = {
        '--prod-primary': theme['primary'],
        '--prod-secondary': theme['secondary'],
        '--prod-bg': theme['bg'],
        '--prod-text': theme['text'],
        '--prod-button-text': theme['button_text'],
        '--prod-button-bg': theme['button_bg'],
        '--prod-muted': theme['muted'],
        '--prod-line': theme['line'],
        '--prod-panel-flat': theme['panel_flat'],
        '--prod-panel': theme['panel_flat'],
        '--prod-info': theme['info'],
        '--prod-shadow-lg': shadow_lg,
        '--prod-shadow-md': shadow_md,
        '--prod-system-image': system_image_value,
        '--prod-font-ui': font_ui,
        '--prod-font-display': font_display,
        '--prod-font-weight': font_weight_values[theme['font_weight']],
        '--prod-font-style': theme['font_style'],
        '--prod-text-decoration': theme['font_decoration'],
        '--prod-font-size-base': font_size_base,
        '--prod-font-size-scale': font_size_scale,
    }
    css_vars_light = {
        '--prod-bg': theme['bg_light'],
        '--prod-text': theme['text_light'],
        '--prod-button-text': theme['button_text'],
        '--prod-button-bg': theme['button_bg'],
        # En tema claro, el muted debe oscurecerse para ser legible.
        '--prod-muted': 'rgba(15, 23, 42, 0.72)',
        '--prod-muted-soft': 'rgba(15, 23, 42, 0.82)',
        '--prod-line': theme['line'],
        '--prod-panel-flat': theme['panel_flat'],
        '--prod-panel': theme['panel_flat'],
        '--prod-shadow-lg': shadow_lg,
        '--prod-shadow-md': shadow_md,
        '--prod-system-image': system_image_value,
        '--prod-font-ui': font_ui,
        '--prod-font-display': font_display,
        '--prod-font-weight': font_weight_values[theme['font_weight']],
        '--prod-font-style': theme['font_style'],
        '--prod-text-decoration': theme['font_decoration'],
        '--prod-font-size-base': font_size_base,
        '--prod-font-size-scale': font_size_scale,
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
        from football.models import Workspace, WorkspaceMembership  # noqa: WPS433 (lazy import)
    except Exception:
        return {}

    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    workspace = workspace_context.get_active_workspace(request)
    # Platform admins: si no hay workspace activo (por diseño), pero el sistema solo tiene
    # un cliente club, lo fijamos para que la navegación (Admin/Categorías) sea consistente.
    if not workspace:
        try:
            is_admin_user = bool(workspace_context.is_admin_user(request.user))
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
                logger.debug('No se pudo fijar el unico workspace club para admin %s', getattr(request.user, 'id', None), exc_info=True)
    active_team = workspace_context.get_active_team_for_request(request)
    active_team_query = ''
    try:
        if active_team and getattr(active_team, 'id', None):
            active_team_query = f'?team={int(active_team.id)}'
    except Exception:
        active_team_query = ''
    badge = workspace_ui.build_active_workspace_badge(request)
    entry_url = workspace_ui.workspace_entry_url(workspace, user=request.user) if workspace else ''
    try:
        from django.urls import reverse  # noqa: WPS433 (lazy import)
        club_dashboard_url = reverse('dashboard-home')
        if workspace_context.can_access_platform(request.user):
            club_dashboard_url = f'{club_dashboard_url}?home=club'
    except Exception:
        club_dashboard_url = ''
    can_manage = False
    is_admin = False
    can_access_staff = False
    try:
        can_manage = bool(workspace_context.can_manage_workspace(request.user, workspace)) if workspace else False
        is_admin = bool(workspace_context.is_admin_user(request.user))
        # Staff (cuerpo técnico) debe ser accesible para perfiles técnicos aunque el workspace o el menú varíen.
        # Usamos la misma lógica que el backend para permitir/denegar el acceso.
        can_access_staff = bool(permissions.can_access_coach_workspace(request.user))
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
        defaults = permissions.workspace_default_modules(kind)
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
            user_is_platform = bool(workspace_context.can_access_platform(request.user))
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
            links = workspace_context.workspace_team_links_for_user(workspace, request.user)
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
                workspace_context.available_workspaces_for_user(request.user)
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
                logger.debug('No se pudo guardar opciones de workspace en cache %s', ws_cache_key, exc_info=True)
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
            logger.debug('No se pudo guardar payload de workspace access en cache %s', ctx_cache_key, exc_info=True)
    return payload
