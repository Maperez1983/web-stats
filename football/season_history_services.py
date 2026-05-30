from __future__ import annotations

from django.utils import timezone

from .models import Player, Workspace, WorkspaceSeason, WorkspaceSeasonPlayer, WorkspaceSeasonTeam, WorkspaceTeam


def active_club_season(workspace):
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return None
    season = getattr(workspace, 'active_season', None)
    if season and bool(getattr(season, 'is_active', True)):
        return season
    return None


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
