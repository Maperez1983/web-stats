from django.db import migrations
from django.db.models import Q


def backfill_club_seasons(apps, schema_editor):
    Workspace = apps.get_model('football', 'Workspace')
    WorkspaceSeason = apps.get_model('football', 'WorkspaceSeason')
    WorkspaceTeam = apps.get_model('football', 'WorkspaceTeam')
    Match = apps.get_model('football', 'Match')
    TrainingSession = apps.get_model('football', 'TrainingSession')
    SessionTask = apps.get_model('football', 'SessionTask')
    TacticalPlaybookClip = apps.get_model('football', 'TacticalPlaybookClip')
    RivalVideo = apps.get_model('football', 'RivalVideo')
    AnalysisVideoReport = apps.get_model('football', 'AnalysisVideoReport')
    RivalAnalysisReport = apps.get_model('football', 'RivalAnalysisReport')

    def _as_date(value):
        if hasattr(value, 'date'):
            return value.date()
        return value

    def _season_for_date(seasons, value):
        value = _as_date(value)
        if not value:
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

    for workspace in Workspace.objects.filter(kind='club'):
        team_ids = list(WorkspaceTeam.objects.filter(workspace=workspace).values_list('team_id', flat=True))
        if not team_ids:
            continue
        seasons = list(WorkspaceSeason.objects.filter(workspace=workspace).order_by('-is_active', '-start_date', '-id'))
        if not seasons:
            continue
        specs = [
            (Match.objects.filter(Q(home_team_id__in=team_ids) | Q(away_team_id__in=team_ids), club_season__isnull=True), 'date'),
            (TrainingSession.objects.filter(microcycle__team_id__in=team_ids, club_season__isnull=True), 'session_date'),
            (TacticalPlaybookClip.objects.filter(team_id__in=team_ids, club_season__isnull=True), 'created_at'),
            (RivalVideo.objects.filter(team_id__in=team_ids, club_season__isnull=True), 'created_at'),
            (AnalysisVideoReport.objects.filter(team_id__in=team_ids, club_season__isnull=True), 'created_at'),
            (RivalAnalysisReport.objects.filter(team_id__in=team_ids, club_season__isnull=True), 'created_at'),
        ]
        for qs, field_name in specs:
            for record in qs.only('id', field_name):
                season = _season_for_date(seasons, getattr(record, field_name, None))
                if season:
                    record.club_season_id = season.id
                    record.save(update_fields=['club_season'])

        task_qs = (
            SessionTask.objects
            .filter(session__microcycle__team_id__in=team_ids, club_season__isnull=True)
            .select_related('session')
        )
        for task in task_qs.only('id', 'club_season', 'session__club_season', 'session__session_date'):
            if getattr(task.session, 'club_season_id', None):
                task.club_season_id = task.session.club_season_id
            else:
                season = _season_for_date(seasons, getattr(task.session, 'session_date', None))
                if season:
                    task.club_season_id = season.id
            if task.club_season_id:
                task.save(update_fields=['club_season'])


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0131_workspaceplayer_workspaceseasonplayer_team_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_club_seasons, migrations.RunPython.noop),
    ]
