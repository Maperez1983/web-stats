from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Player, Workspace, WorkspacePlayer, WorkspaceSeason, WorkspaceSeasonPlayer, WorkspaceSeasonTeam, WorkspaceTeam


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


def infer_club_season_for_date(workspace, value):
    if not workspace or not value:
        return None
    if hasattr(value, 'date'):
        value = value.date()
    if not isinstance(value, date):
        return None
    return (
        WorkspaceSeason.objects
        .filter(workspace=workspace, start_date__lte=value)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=value))
        .order_by('-is_active', '-start_date', '-id')
        .first()
    )


def selected_club_season_is_read_only(season):
    return bool(season and not getattr(season, 'is_active', False))


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


def ensure_workspace_player(workspace, player, *, current_team=None, is_active=True):
    if not workspace or not player:
        return None
    if current_team:
        try:
            allowed = WorkspaceTeam.objects.filter(workspace=workspace, team=current_team).exists()
        except Exception:
            allowed = False
        if not allowed:
            current_team = None
    membership, created = WorkspacePlayer.objects.get_or_create(
        workspace=workspace,
        player=player,
        defaults={
            'current_team': current_team,
            'is_active': bool(is_active),
        },
    )
    updates = []
    if not created:
        if current_team and getattr(membership, 'current_team_id', None) != getattr(current_team, 'id', None):
            membership.current_team = current_team
            updates.append('current_team')
        if membership.is_active != bool(is_active):
            membership.is_active = bool(is_active)
            updates.append('is_active')
        if updates:
            updates.append('updated_at')
            membership.save(update_fields=sorted(set(updates)))
    return membership


def workspace_players_for_team(workspace, team, *, compatible_only=True):
    if not workspace:
        return WorkspacePlayer.objects.none()
    qs = WorkspacePlayer.objects.filter(workspace=workspace, is_active=True).select_related('player', 'current_team')
    if compatible_only and team:
        qs = qs.filter(Q(current_team=team) | Q(player__team=team))
    return qs.order_by('player__number', 'player__name', 'id')


@transaction.atomic
def close_workspace_season(workspace, *, season=None, end_date=None):
    season = season or active_club_season(workspace)
    if not workspace or not season:
        raise ValueError('No hay temporada activa para cerrar.')
    end_date = end_date or timezone.localdate()
    season.end_date = end_date
    season.is_active = False
    season.archived_at = timezone.now()
    season.save(update_fields=['end_date', 'is_active', 'archived_at', 'updated_at'])
    if getattr(workspace, 'active_season_id', None) == season.id:
        workspace.active_season = None
        workspace.save(update_fields=['active_season', 'updated_at'])
    return season


@transaction.atomic
def open_workspace_season(
    workspace,
    *,
    label,
    start_date,
    end_date=None,
    team=None,
    inherit_teams=True,
    inherit_roster=True,
):
    if not workspace:
        raise ValueError('Falta el club para crear la temporada.')
    label = str(label or '').strip()
    if not label:
        raise ValueError('Etiqueta de temporada obligatoria.')
    if not start_date:
        raise ValueError('Fecha de inicio obligatoria.')

    WorkspaceSeason.objects.filter(workspace=workspace, is_active=True).exclude(label=label).update(is_active=False)
    season, _created = WorkspaceSeason.objects.update_or_create(
        workspace=workspace,
        label=label,
        defaults={
            'start_date': start_date,
            'end_date': end_date,
            'is_active': True,
            'archived_at': None,
        },
    )
    workspace.active_season = season
    workspace.save(update_fields=['active_season', 'updated_at'])

    if inherit_teams:
        ensure_active_workspace_team_seasons(workspace, season=season)
    elif team:
        ensure_season_team(season, team)

    if inherit_roster:
        roster_teams = [team] if team else [
            link.team
            for link in WorkspaceTeam.objects.filter(workspace=workspace).select_related('team')
            if getattr(link, 'team', None)
        ]
        for roster_team in roster_teams:
            ensure_team_roster_season_memberships(season, roster_team, include_inactive=True)
    return season


def ensure_player_season_membership(season, player, *, team=None, confirmed=False, status=None):
    if not season or not player:
        return None
    workspace = getattr(season, 'workspace', None)
    if workspace:
        ensure_workspace_player(workspace, player, current_team=team or getattr(player, 'team', None), is_active=getattr(player, 'is_active', True))
    if team and workspace:
        try:
            if not WorkspaceTeam.objects.filter(workspace=workspace, team=team).exists():
                team = None
        except Exception:
            team = None
    status = status or (WorkspaceSeasonPlayer.STATUS_CONFIRMED if confirmed else WorkspaceSeasonPlayer.STATUS_PENDING)
    membership, created = WorkspaceSeasonPlayer.objects.get_or_create(
        season=season,
        player=player,
        defaults={
            'team': team,
            'is_confirmed': bool(confirmed),
            'status': status,
            'confirmed_at': timezone.now() if confirmed else None,
        },
    )
    updates = []
    if team and getattr(membership, 'team_id', None) != getattr(team, 'id', None):
        membership.team = team
        updates.append('team')
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
        membership = ensure_player_season_membership(season, player, team=team, confirmed=False, status=status)
        if membership:
            memberships.append(membership)
    return memberships


def mark_player_left_current_season(season, player, *, notes=''):
    if not season or not player:
        return None
    membership = ensure_player_season_membership(season, player, team=getattr(player, 'team', None), confirmed=False, status=WorkspaceSeasonPlayer.STATUS_LEFT)
    if membership:
        membership.is_confirmed = False
        membership.left_at = timezone.now()
        membership.status = WorkspaceSeasonPlayer.STATUS_LEFT
        membership.status_notes = str(notes or '')[:220]
        membership.save(update_fields=['is_confirmed', 'status', 'left_at', 'status_notes', 'updated_at'])
    WorkspacePlayer.objects.filter(workspace=season.workspace, player=player).update(is_active=False)
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
        .select_related('season', 'season__workspace', 'team')
        .order_by('-season__start_date', '-season_id')
    )


def _season_for_record_date(seasons, value):
    if hasattr(value, 'date'):
        value = value.date()
    if not isinstance(value, date):
        return None
    for season in seasons:
        start = getattr(season, 'start_date', None)
        end = getattr(season, 'end_date', None)
        if start and value < start:
            continue
        if end and value > end:
            continue
        return season
    return None


def season_architecture_audit(workspace):
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return {}

    from .models import AnalysisVideoReport, Match, RivalAnalysisReport, RivalVideo, SessionTask, TacticalPlaybookClip, TrainingSession

    team_ids = list(
        WorkspaceTeam.objects
        .filter(workspace=workspace)
        .values_list('team_id', flat=True)
    )
    seasons = list(WorkspaceSeason.objects.filter(workspace=workspace).order_by('-is_active', '-start_date', '-id'))
    summary = {
        'workspace_id': int(workspace.id),
        'season_count': len(seasons),
        'active_season_id': int(getattr(workspace, 'active_season_id', 0) or 0),
        'models': {},
    }
    if not team_ids:
        return summary

    specs = _season_backfill_specs(team_ids)
    for key, qs, field_name in specs:
        total = 0
        explicit = 0
        without_date = 0
        outside_seasons = 0
        by_season = {}
        for record in qs.only('id', field_name, 'club_season').distinct():
            total += 1
            explicit_season_id = int(getattr(record, 'club_season_id', 0) or 0)
            if explicit_season_id:
                explicit += 1
                season_key = str(explicit_season_id)
                by_season[season_key] = by_season.get(season_key, 0) + 1
                continue
            value = getattr(record, field_name, None)
            if not value:
                without_date += 1
                continue
            season = _season_for_record_date(seasons, value)
            if not season:
                outside_seasons += 1
                continue
            season_key = str(int(season.id))
            by_season[season_key] = by_season.get(season_key, 0) + 1
        summary['models'][key] = {
            'total': total,
            'explicit': explicit,
            'implicit': max(0, total - explicit),
            'without_date': without_date,
            'outside_seasons': outside_seasons,
            'by_season': by_season,
        }
    total = 0
    explicit = 0
    without_date = 0
    outside_seasons = 0
    by_season = {}
    task_rows = (
        SessionTask.objects
        .filter(session__microcycle__team_id__in=team_ids)
        .select_related('session')
        .only('id', 'club_season', 'session__session_date')
        .distinct()
    )
    for task in task_rows:
        total += 1
        explicit_season_id = int(getattr(task, 'club_season_id', 0) or 0)
        if explicit_season_id:
            explicit += 1
            season_key = str(explicit_season_id)
            by_season[season_key] = by_season.get(season_key, 0) + 1
            continue
        session_date = getattr(getattr(task, 'session', None), 'session_date', None)
        if not session_date:
            without_date += 1
            continue
        season = _season_for_record_date(seasons, session_date)
        if not season:
            outside_seasons += 1
            continue
        season_key = str(int(season.id))
        by_season[season_key] = by_season.get(season_key, 0) + 1
    summary['models']['session_tasks'] = {
        'total': total,
        'explicit': explicit,
        'implicit': max(0, total - explicit),
        'without_date': without_date,
        'outside_seasons': outside_seasons,
        'by_season': by_season,
    }
    return summary


def _season_backfill_specs(team_ids):
    from .models import AnalysisVideoReport, Match, RivalAnalysisReport, RivalVideo, TacticalPlaybookClip, TrainingSession

    return [
        ('matches', Match.objects.filter(home_team_id__in=team_ids) | Match.objects.filter(away_team_id__in=team_ids), 'date'),
        ('sessions', TrainingSession.objects.filter(microcycle__team_id__in=team_ids), 'session_date'),
        ('playbook_clips', TacticalPlaybookClip.objects.filter(team_id__in=team_ids), 'created_at'),
        ('rival_videos', RivalVideo.objects.filter(team_id__in=team_ids), 'created_at'),
        ('analysis_reports', AnalysisVideoReport.objects.filter(team_id__in=team_ids), 'created_at'),
        ('rival_reports', RivalAnalysisReport.objects.filter(team_id__in=team_ids), 'created_at'),
    ]


def backfill_workspace_club_seasons(workspace, *, dry_run=True):
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return {}
    team_ids = list(
        WorkspaceTeam.objects
        .filter(workspace=workspace)
        .values_list('team_id', flat=True)
    )
    seasons = list(WorkspaceSeason.objects.filter(workspace=workspace).order_by('-is_active', '-start_date', '-id'))
    result = {
        'workspace_id': int(workspace.id),
        'dry_run': bool(dry_run),
        'models': {},
    }
    if not team_ids or not seasons:
        return result

    for key, qs, field_name in _season_backfill_specs(team_ids):
        updated = 0
        skipped_with_season = 0
        without_date = 0
        outside_seasons = 0
        for record in qs.filter(club_season__isnull=True).only('id', field_name, 'club_season').distinct():
            value = getattr(record, field_name, None)
            if not value:
                without_date += 1
                continue
            season = _season_for_record_date(seasons, value)
            if not season:
                outside_seasons += 1
                continue
            updated += 1
            if not dry_run:
                record.club_season = season
                record.save(update_fields=['club_season'])
        try:
            skipped_with_season = qs.filter(club_season__isnull=False).distinct().count()
        except Exception:
            skipped_with_season = 0
        result['models'][key] = {
            'assigned': updated,
            'already_assigned': skipped_with_season,
            'without_date': without_date,
            'outside_seasons': outside_seasons,
        }

    # Las tareas heredan explícitamente la temporada de la sesión si todavía quedaron sin asignar.
    from .models import SessionTask

    tasks_qs = (
        SessionTask.objects
        .filter(session__microcycle__team_id__in=team_ids, club_season__isnull=True, session__club_season__isnull=False)
        .select_related('session')
    )
    task_assigned = tasks_qs.count()
    if not dry_run:
        for task in tasks_qs.only('id', 'club_season', 'session__club_season'):
            task.club_season_id = task.session.club_season_id
            task.save(update_fields=['club_season'])
    task_report = result['models'].setdefault('session_tasks', {})
    task_report['assigned_from_session'] = task_assigned
    remaining_qs = (
        SessionTask.objects
        .filter(session__microcycle__team_id__in=team_ids, club_season__isnull=True)
        .select_related('session')
    )
    inferred_from_date = 0
    without_date = 0
    outside_seasons = 0
    for task in remaining_qs.only('id', 'club_season', 'session__session_date'):
        session_date = getattr(getattr(task, 'session', None), 'session_date', None)
        if not session_date:
            without_date += 1
            continue
        season = _season_for_record_date(seasons, session_date)
        if not season:
            outside_seasons += 1
            continue
        inferred_from_date += 1
        if not dry_run:
            task.club_season = season
            task.save(update_fields=['club_season'])
    task_report['assigned_from_date'] = inferred_from_date
    task_report['without_date'] = task_report.get('without_date', 0) + without_date
    task_report['outside_seasons'] = task_report.get('outside_seasons', 0) + outside_seasons
    return result
