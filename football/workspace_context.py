import logging
import os

from django.db.models import Q

from .access_policy import can_manage_workspace as policy_can_manage_workspace
from .access_policy import can_view_workspace as policy_can_view_workspace
from .access_policy import workspace_membership_for_user as policy_workspace_membership_for_user
from .models import AppUserRole, StaffMember, Team, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess
from .services import _parse_int


_REQUEST_CACHE_MISSING = object()
logger = logging.getLogger(__name__)


def _request_cache_get(request, attr_name):
    try:
        if request is not None and hasattr(request, attr_name):
            return getattr(request, attr_name)
    except Exception:
        logger.debug('No se pudo leer cache de request %s', attr_name, exc_info=True)
    return _REQUEST_CACHE_MISSING


def _request_cache_set(request, attr_name, value):
    try:
        if request is not None:
            setattr(request, attr_name, value)
    except Exception:
        logger.debug('No se pudo escribir cache de request %s', attr_name, exc_info=True)
    return value


def _cache_active_workspace(request, workspace):
    return _request_cache_set(request, "_cached_active_workspace", workspace)


def _cache_active_team(request, team):
    return _request_cache_set(request, "_cached_active_team", team)


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    role_obj = getattr(user, 'app_role', None)
    role = str(getattr(role_obj, 'role', '') or '').strip() or None
    legacy_map = {
        'admin': AppUserRole.ROLE_ADMIN,
        'player': AppUserRole.ROLE_PLAYER,
    }
    normalized_role = legacy_map.get(role, role)
    if normalized_role:
        return normalized_role
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return AppUserRole.ROLE_ADMIN
    return None


def is_admin_user(user):
    role = get_user_role(user)
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff or role == AppUserRole.ROLE_ADMIN))


def can_access_platform(user):
    return is_admin_user(user)


def available_workspaces_for_user(user):
    if not user or not user.is_authenticated:
        return Workspace.objects.none()
    qs = Workspace.objects.select_related('primary_team', 'owner_user').filter(is_active=True)
    if can_access_platform(user):
        return qs
    return qs.filter(Q(memberships__user=user) | Q(owner_user=user)).distinct()


def single_club_fallback_enabled() -> bool:
    return str(os.getenv('ALLOW_SINGLE_CLUB_FALLBACK', '0') or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def get_active_workspace(request):
    cached = _request_cache_get(request, "_cached_active_workspace")
    if cached is not _REQUEST_CACHE_MISSING:
        return cached
    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return _cache_active_workspace(request, None)
    available_qs = available_workspaces_for_user(request.user)
    workspace_id = _parse_int(request.GET.get('workspace') or request.POST.get('workspace'))
    if not workspace_id:
        workspace_id = _parse_int(request.session.get('active_workspace_id'))
    if workspace_id:
        workspace = available_qs.filter(id=workspace_id).first()
        if workspace:
            request.session['active_workspace_id'] = workspace.id
            return _cache_active_workspace(request, workspace)
        request.session.pop('active_workspace_id', None)
    if can_access_platform(request.user):
        try:
            wants_club_home = str(request.GET.get('home') or '').strip().lower() == 'club'
        except Exception:
            wants_club_home = False
        if wants_club_home:
            try:
                club_qs = available_qs.filter(kind=Workspace.KIND_CLUB, is_active=True)
                preferred = (
                    club_qs.filter(owner_user=request.user).order_by('id').first()
                    or club_qs.filter(memberships__user=request.user).order_by('id').first()
                    or club_qs.order_by('id').first()
                )
                if preferred:
                    request.session['active_workspace_id'] = preferred.id
                    return _cache_active_workspace(request, preferred)
            except Exception:
                logger.debug('No se pudo resolver workspace club preferido para usuario %s', getattr(request.user, 'id', None), exc_info=True)
        try:
            club_ws = list(
                available_qs
                .filter(kind=Workspace.KIND_CLUB, is_active=True)
                .order_by('id')[:2]
            )
            if len(club_ws) == 1:
                workspace = club_ws[0]
                request.session['active_workspace_id'] = workspace.id
                return _cache_active_workspace(request, workspace)
        except Exception:
            logger.debug('No se pudo autoasignar el unico workspace club disponible', exc_info=True)
        if single_club_fallback_enabled():
            try:
                club_ws = list(
                    Workspace.objects
                    .filter(kind=Workspace.KIND_CLUB, is_active=True)
                    .order_by('id')[:2]
                )
                if len(club_ws) == 1:
                    workspace = club_ws[0]
                    request.session['active_workspace_id'] = workspace.id
                    return _cache_active_workspace(request, workspace)
            except Exception:
                logger.debug('No se pudo aplicar fallback monoclub para workspace activo', exc_info=True)
        return _cache_active_workspace(request, None)

    if single_club_fallback_enabled():
        try:
            role = get_user_role(request.user)
            if role and role != AppUserRole.ROLE_PLAYER:
                club_ws = list(Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).order_by('id')[:2])
                if len(club_ws) == 1:
                    club = club_ws[0]
                    if not WorkspaceMembership.objects.filter(workspace=club, user=request.user).exists() and int(getattr(club, 'owner_user_id', 0) or 0) != int(request.user.id):
                        WorkspaceMembership.objects.get_or_create(
                            workspace=club,
                            user=request.user,
                            defaults={'role': WorkspaceMembership.ROLE_VIEWER},
                        )
        except Exception:
            logger.debug('No se pudo crear membresia viewer de fallback para usuario %s', getattr(request.user, 'id', None), exc_info=True)
    fallback_workspace = available_qs.order_by('kind', 'name', 'id').first()
    if fallback_workspace:
        request.session['active_workspace_id'] = fallback_workspace.id
        return _cache_active_workspace(request, fallback_workspace)
    if single_club_fallback_enabled():
        role = get_user_role(request.user)
        if role in {AppUserRole.ROLE_PLAYER, AppUserRole.ROLE_COACH, AppUserRole.ROLE_FITNESS, AppUserRole.ROLE_GOALKEEPER, AppUserRole.ROLE_ANALYST}:
            club_ws = list(Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).order_by('id')[:2])
            if len(club_ws) == 1:
                workspace = club_ws[0]
                try:
                    WorkspaceMembership.objects.get_or_create(
                        workspace=workspace,
                        user=request.user,
                        defaults={'role': WorkspaceMembership.ROLE_MEMBER},
                    )
                except Exception:
                    logger.debug('No se pudo crear membresia member de fallback para usuario %s', getattr(request.user, 'id', None), exc_info=True)
                request.session['active_workspace_id'] = workspace.id
                return _cache_active_workspace(request, workspace)
    return _cache_active_workspace(request, None)


def workspace_team_links(workspace):
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return []
    try:
        links = list(
            WorkspaceTeam.objects.filter(workspace=workspace)
            .select_related('team')
            .order_by('-is_default', 'team__name', 'id')
        )
    except Exception:
        links = []
    if not links and getattr(workspace, 'primary_team_id', None):
        try:
            WorkspaceTeam.objects.get_or_create(
                workspace_id=workspace.id,
                team_id=workspace.primary_team_id,
                defaults={'is_default': True},
            )
            links = list(
                WorkspaceTeam.objects.filter(workspace=workspace)
                .select_related('team')
                .order_by('-is_default', 'team__name', 'id')
            )
        except Exception:
            links = []
    return links


def workspace_team_links_for_user(workspace, user):
    links = workspace_team_links(workspace)
    if not links or not workspace or workspace.kind != Workspace.KIND_CLUB:
        return links
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    if can_manage_workspace(user, workspace):
        return links
    try:
        access_rows = list(
            WorkspaceTeamAccess.objects
            .filter(workspace=workspace, user=user)
            .values_list('team_id', 'is_default')
        )
    except Exception:
        access_rows = []
    if access_rows:
        allowed_team_ids = {int(team_id) for (team_id, _) in access_rows if team_id}
        return [link for link in links if int(getattr(link, 'team_id', 0) or 0) in allowed_team_ids]
    staff_team_ids = staff_team_ids_for_user(workspace, user)
    if staff_team_ids:
        return [link for link in links if int(getattr(link, 'team_id', 0) or 0) in staff_team_ids]
    default_link = next((link for link in links if getattr(link, 'is_default', False)), None)
    if default_link:
        return [default_link]
    return links[:1]


def staff_team_ids_for_user(workspace, user):
    if not workspace or not user or not getattr(user, 'is_authenticated', False):
        return set()
    try:
        return {
            int(team_id)
            for team_id in (
                StaffMember.objects
                .filter(workspace=workspace, user=user, is_active=True, team__isnull=False)
                .values_list('team_id', flat=True)
            )
            if team_id
        }
    except Exception:
        logger.debug(
            'No se pudieron resolver equipos staff para usuario %s en workspace %s',
            getattr(user, 'id', None),
            getattr(workspace, 'id', None),
            exc_info=True,
        )
        return set()


def allowed_team_ids_for_request(request):
    workspace = get_active_workspace(request)
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return set()
    links = workspace_team_links_for_user(workspace, getattr(request, 'user', None))
    return {int(getattr(link, 'team_id', 0) or 0) for link in links if getattr(link, 'team_id', None)}


def user_can_access_team(request, team: "Team") -> bool:
    if not team or not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return False
    try:
        if can_access_platform(request.user):
            return True
    except Exception:
        logger.debug('No se pudo evaluar acceso platform del usuario %s', getattr(request.user, 'id', None), exc_info=True)
    allowed_team_ids = allowed_team_ids_for_request(request)
    if allowed_team_ids:
        try:
            return int(team.id) in {int(tid) for tid in allowed_team_ids}
        except Exception:
            return False
    try:
        if WorkspaceTeamAccess.objects.filter(user=request.user, team=team).exists():
            return True
    except Exception:
        logger.debug(
            'No se pudo comprobar acceso explicito del usuario %s al equipo %s',
            getattr(request.user, 'id', None),
            getattr(team, 'id', None),
            exc_info=True,
        )
    try:
        if WorkspaceTeam.objects.filter(team=team, workspace__is_active=True, workspace__owner_user=request.user).exists():
            return True
        return WorkspaceTeam.objects.filter(team=team, workspace__is_active=True, workspace__memberships__user=request.user).exists()
    except Exception:
        return False


def team_from_request_param(request):
    if not request:
        return None
    team_id = _parse_int(request.GET.get("team") or request.GET.get("team_id") or request.POST.get("team") or request.POST.get("team_id"))
    if team_id:
        team = Team.objects.filter(id=team_id).first()
        if team and user_can_access_team(request, team):
            workspace = get_active_workspace(request)
            if workspace and workspace.kind == Workspace.KIND_CLUB and hasattr(request, "session"):
                try:
                    mapping = request.session.get("active_team_by_workspace")
                    if not isinstance(mapping, dict):
                        mapping = {}
                    mapping[str(workspace.id)] = int(team.id)
                    request.session["active_team_by_workspace"] = mapping
                except Exception:
                    logger.debug(
                        'No se pudo recordar equipo activo %s para workspace %s',
                        getattr(team, 'id', None),
                        getattr(workspace, 'id', None),
                        exc_info=True,
                    )
            return team
    team_slug = str(request.GET.get("team_slug") or request.POST.get("team_slug") or "").strip()
    if team_slug:
        team = Team.objects.filter(slug=team_slug).first()
        if team and user_can_access_team(request, team):
            return team
    return None


def get_active_team_for_request(request):
    cached = _request_cache_get(request, "_cached_active_team")
    if cached is not _REQUEST_CACHE_MISSING:
        return cached
    workspace = get_active_workspace(request)
    if not workspace and request and hasattr(request, 'session') and getattr(request, 'user', None) and request.user.is_authenticated:
        try:
            remembered_team_id = _parse_int(request.session.get('active_team_id'))
        except Exception:
            remembered_team_id = None
        if remembered_team_id:
            remembered_team = Team.objects.filter(id=int(remembered_team_id)).first()
            if remembered_team and user_can_access_team(request, remembered_team):
                return _cache_active_team(request, remembered_team)

    if workspace and workspace.kind == Workspace.KIND_CLUB:
        links = workspace_team_links_for_user(workspace, request.user)
        team_lookup = {int(link.team_id): link.team for link in links if getattr(link, 'team_id', None)}
        desired_team_id = _parse_int(
            request.GET.get('team')
            or request.GET.get('team_id')
            or request.GET.get('active_team_id')
            or request.POST.get('team')
            or request.POST.get('team_id')
            or request.POST.get('active_team_id')
        )
        mapping = request.session.get('active_team_by_workspace') if request and hasattr(request, 'session') else None
        if not desired_team_id and isinstance(mapping, dict):
            desired_team_id = _parse_int(mapping.get(str(workspace.id)) or mapping.get(workspace.id))
        if desired_team_id and int(desired_team_id) in team_lookup:
            explicit_team_param = bool(
                request
                and (
                    request.GET.get('team')
                    or request.GET.get('team_id')
                    or request.GET.get('active_team_id')
                )
            )
            if explicit_team_param and hasattr(request, 'session'):
                try:
                    if not isinstance(mapping, dict):
                        mapping = {}
                    mapping[str(workspace.id)] = int(desired_team_id)
                    request.session['active_team_by_workspace'] = mapping
                except Exception:
                    logger.debug(
                        'No se pudo recordar equipo activo %s para workspace %s',
                        desired_team_id,
                        getattr(workspace, 'id', None),
                        exc_info=True,
                    )
            team = team_lookup[int(desired_team_id)]
            return _cache_active_team(request, team)
        try:
            if request and getattr(request, 'user', None) and request.user.is_authenticated and workspace:
                preferred_team_id = (
                    WorkspaceTeamAccess.objects
                    .filter(workspace=workspace, user=request.user, is_default=True)
                    .values_list('team_id', flat=True)
                    .first()
                )
                if preferred_team_id and int(preferred_team_id) in team_lookup:
                    team = team_lookup[int(preferred_team_id)]
                    return _cache_active_team(request, team)
        except Exception:
            logger.debug('No se pudo resolver equipo preferido para workspace %s', getattr(workspace, 'id', None), exc_info=True)
        default_link = next((link for link in links if getattr(link, 'is_default', False)), None)
        if default_link and getattr(default_link, 'team', None):
            team = default_link.team
            return _cache_active_team(request, team)
        if getattr(workspace, 'primary_team_id', None) and int(getattr(workspace, 'primary_team_id', 0) or 0) in team_lookup:
            team = workspace.primary_team
            return _cache_active_team(request, team)
        first_link = links[0].team if links else None
        if first_link:
            return _cache_active_team(request, first_link)
        return None

    if request and getattr(request, 'user', None) and request.user.is_authenticated and not can_access_platform(request.user):
        try:
            explicit_team = team_from_request_param(request)
        except Exception:
            logger.debug('No se pudo resolver equipo explicito desde request', exc_info=True)
            explicit_team = None
        if explicit_team:
            try:
                if hasattr(request, 'session'):
                    request.session['active_team_id'] = int(explicit_team.id)
            except Exception:
                logger.debug('No se pudo guardar active_team_id %s en sesion', getattr(explicit_team, 'id', None), exc_info=True)
            return _cache_active_team(request, explicit_team)
        remembered_team_id = None
        try:
            if hasattr(request, 'session'):
                remembered_team_id = _parse_int(request.session.get('active_team_id'))
        except Exception:
            remembered_team_id = None
        team_ids = set()
        try:
            team_ids.update(WorkspaceTeamAccess.objects.filter(user=request.user).values_list('team_id', flat=True))
        except Exception:
            logger.debug('No se pudo cargar accesos directos a equipos para usuario %s', getattr(request.user, 'id', None), exc_info=True)
        if not team_ids:
            try:
                team_ids.update(WorkspaceTeam.objects.filter(workspace__is_active=True, workspace__owner_user=request.user).values_list('team_id', flat=True))
            except Exception:
                logger.debug('No se pudo cargar equipos por ownership para usuario %s', getattr(request.user, 'id', None), exc_info=True)
        if not team_ids:
            try:
                team_ids.update(WorkspaceTeam.objects.filter(workspace__is_active=True, workspace__memberships__user=request.user).values_list('team_id', flat=True))
            except Exception:
                logger.debug('No se pudo cargar equipos por membresia para usuario %s', getattr(request.user, 'id', None), exc_info=True)
        team_ids = {int(tid) for tid in team_ids if tid}
        if remembered_team_id and int(remembered_team_id) in team_ids:
            team = Team.objects.filter(id=int(remembered_team_id)).first()
            if team:
                return _cache_active_team(request, team)
        if len(team_ids) == 1:
            team = Team.objects.filter(id=next(iter(team_ids))).first()
            if team:
                try:
                    if hasattr(request, 'session'):
                        request.session['active_team_id'] = int(team.id)
                except Exception:
                    logger.debug('No se pudo guardar unico active_team_id %s en sesion', getattr(team, 'id', None), exc_info=True)
            return _cache_active_team(request, team)
        if team_ids:
            try:
                fallback_team_id = max(int(tid) for tid in team_ids if tid)
            except Exception:
                fallback_team_id = None
            if fallback_team_id:
                team = Team.objects.filter(id=int(fallback_team_id)).first()
                if team:
                    try:
                        if hasattr(request, 'session'):
                            request.session['active_team_id'] = int(team.id)
                    except Exception:
                        logger.debug('No se pudo guardar fallback active_team_id %s en sesion', getattr(team, 'id', None), exc_info=True)
                    return _cache_active_team(request, team)
        if single_club_fallback_enabled():
            team = Team.objects.filter(is_primary=True).first()
            return _cache_active_team(request, team)
        return None
    team = Team.objects.filter(is_primary=True).first() if single_club_fallback_enabled() else None
    return _cache_active_team(request, team)


def workspace_membership_for_user(workspace, user):
    return policy_workspace_membership_for_user(workspace, user)


def can_view_workspace(user, workspace):
    return policy_can_view_workspace(user, workspace, platform_access=can_access_platform(user))


def can_manage_workspace(user, workspace):
    return policy_can_manage_workspace(user, workspace, platform_access=can_access_platform(user))
