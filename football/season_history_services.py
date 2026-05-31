from __future__ import annotations

from django.utils import timezone

from .models import Player, Workspace, WorkspaceSeason, WorkspaceSeasonPlayer, WorkspaceSeasonTeam, WorkspaceTeam


def _int_or_none(value):
    try:
        parsed = int(value or 0)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def active_club_season(workspace):
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return None
    season = getattr(workspace, 'active_season', None)
    if season and bool(getattr(season, 'is_active', True)):
        return season
    return None


def club_season_options_for_workspace(workspace, *, limit=12):
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return []
    qs = WorkspaceSeason.objects.filter(workspace=workspace).order_by('-is_active', '-start_date', '-id')
    options = []
    for season in qs[: max(1, int(limit or 12))]:
        options.append(
            {
                'id': int(season.id),
                'label': str(season.label or '').strip(),
                'is_active': bool(season.is_active),
                'start_date': season.start_date.isoformat() if season.start_date else '',
                'end_date': season.end_date.isoformat() if season.end_date else '',
            }
        )
    return options


def selected_club_season_for_request(request, workspace=None):
    if not workspace:
        try:
            from .workspace_context import get_active_workspace

            workspace = get_active_workspace(request)
        except Exception:
            workspace = None
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return None

    session_key = f'active_club_season_id:{int(workspace.id)}'
    raw_id = None
    try:
        raw_id = request.GET.get('club_season_id')
    except Exception:
        raw_id = None
    selected_id = _int_or_none(raw_id)
    if not selected_id:
        try:
            selected_id = _int_or_none(request.session.get(session_key))
        except Exception:
            selected_id = None

    season = None
    if selected_id:
        season = WorkspaceSeason.objects.filter(workspace=workspace, id=selected_id).first()
    if season:
        try:
            if request and hasattr(request, 'session'):
                request.session[session_key] = int(season.id)
        except Exception:
            pass
        return season
    return active_club_season(workspace)


def club_season_date_bounds(season):
    if not season:
        return None, None
    date_start = getattr(season, 'start_date', None)
    date_end = getattr(season, 'end_date', None)
    if not date_end and bool(getattr(season, 'is_active', False)):
        date_end = timezone.localdate()
    return date_start, date_end


def serialize_club_season(season):
    if not season:
        return {}
    date_start, date_end = club_season_date_bounds(season)
    return {
        'id': int(season.id),
        'label': str(season.label or '').strip(),
        'is_active': bool(season.is_active),
        'start_date': date_start.isoformat() if date_start else '',
        'end_date': date_end.isoformat() if date_end else '',
    }


def ensure_season_team(season, team, *, status=WorkspaceSeasonTeam.STATUS_ACTIVE, is_active=True):
    if not season or not team:
        return None
    membership, created = WorkspaceSeasonTeam.objects.get_or_create(
        season=season,
        team=team,
        defaults={
            'status': status,
            'is_active': bool(is_active),
            'confirmed_at': timezone.now() if is_active else None,
        },
    )
    updates = []
    if not created:
        if membership.status != status:
            membership.status = status
            updates.append('status')
        if membership.is_active != bool(is_active):
            membership.is_active = bool(is_active)
            updates.append('is_active')
        if is_active and not membership.confirmed_at:
            membership.confirmed_at = timezone.now()
            updates.append('confirmed_at')
        if updates:
            updates.append('updated_at')
            membership.save(update_fields=updates)
    return membership


def set_team_season_status(season, team, *, status=WorkspaceSeasonTeam.STATUS_ACTIVE, notes=''):
    if not season or not team:
        return None
    valid_statuses = {choice[0] for choice in WorkspaceSeasonTeam.STATUS_CHOICES}
    status = status if status in valid_statuses else WorkspaceSeasonTeam.STATUS_ACTIVE
    is_active = status == WorkspaceSeasonTeam.STATUS_ACTIVE
    membership = ensure_season_team(season, team, status=status, is_active=is_active)
    if membership:
        membership.notes = str(notes or '')[:500]
        fields = ['notes', 'updated_at']
        if is_active and not membership.confirmed_at:
            membership.confirmed_at = timezone.now()
            fields.append('confirmed_at')
        membership.save(update_fields=sorted(set(fields)))
    return membership


def team_season_membership_map(season, teams):
    if not season or not teams:
        return {}
    team_ids = []
    for team in teams:
        try:
            team_id = int(getattr(team, 'id', None) or getattr(team, 'team_id', None) or 0)
        except Exception:
            team_id = 0
        if team_id:
            team_ids.append(team_id)
    if not team_ids:
        return {}
    rows = (
        WorkspaceSeasonTeam.objects
        .filter(season=season, team_id__in=team_ids)
        .select_related('team')
    )
    return {int(row.team_id): row for row in rows if getattr(row, 'team_id', None)}


def ensure_active_workspace_team_seasons(workspace, *, season=None):
    season = season or active_club_season(workspace)
    if not workspace or not season:
        return []
    links = WorkspaceTeam.objects.filter(workspace=workspace).select_related('team')
    memberships = []
    for link in links:
        membership = ensure_season_team(season, link.team, status=WorkspaceSeasonTeam.STATUS_ACTIVE, is_active=True)
        if membership:
            memberships.append(membership)
    return memberships


def ensure_player_season_membership(season, player, *, confirmed=False, status=None):
    if not season or not player:
        return None
    status = status or (WorkspaceSeasonPlayer.STATUS_CONFIRMED if confirmed else WorkspaceSeasonPlayer.STATUS_PENDING)
    membership, created = WorkspaceSeasonPlayer.objects.get_or_create(
        season=season,
        player=player,
        defaults={
            'is_confirmed': bool(confirmed),
            'status': status,
            'confirmed_at': timezone.now() if confirmed else None,
        },
    )
    updates = []
    terminal_statuses = {WorkspaceSeasonPlayer.STATUS_CONFIRMED, WorkspaceSeasonPlayer.STATUS_LEFT}
    should_preserve_status = not confirmed and membership.status in terminal_statuses
    if not should_preserve_status and membership.status != status:
        membership.status = status
        updates.append('status')
    if confirmed and not membership.is_confirmed:
        membership.is_confirmed = True
        membership.confirmed_at = timezone.now()
        updates.extend(['is_confirmed', 'confirmed_at'])
    if updates:
        updates.append('updated_at')
        membership.save(update_fields=sorted(set(updates)))
    return membership


def ensure_team_roster_season_memberships(season, team, *, include_inactive=True):
    if not season or not team:
        return []
    qs = Player.objects.filter(team=team)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    memberships = []
    for player in qs.only('id', 'is_active'):
        status = WorkspaceSeasonPlayer.STATUS_PENDING if player.is_active else WorkspaceSeasonPlayer.STATUS_INACTIVE
        membership = ensure_player_season_membership(season, player, confirmed=False, status=status)
        if membership:
            memberships.append(membership)
    return memberships


def mark_player_left_current_season(season, player, *, notes=''):
    if not season or not player:
        return None
    membership = ensure_player_season_membership(season, player, confirmed=False, status=WorkspaceSeasonPlayer.STATUS_LEFT)
    if membership:
        membership.is_confirmed = False
        membership.left_at = timezone.now()
        membership.status_notes = str(notes or '')[:220]
        membership.save(update_fields=['is_confirmed', 'status', 'left_at', 'status_notes', 'updated_at'])
    return membership


def team_season_history(team):
    if not team:
        return WorkspaceSeasonTeam.objects.none()
    return (
        WorkspaceSeasonTeam.objects
        .filter(team=team)
        .select_related('season', 'season__workspace')
        .order_by('-season__start_date', '-season_id')
    )


def player_season_history(player):
    if not player:
        return WorkspaceSeasonPlayer.objects.none()
    return (
        WorkspaceSeasonPlayer.objects
        .filter(player=player)
        .select_related('season', 'season__workspace')
        .order_by('-season__start_date', '-season_id')
    )
