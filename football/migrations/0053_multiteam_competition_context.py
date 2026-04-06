from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def _backfill_competition_context_team(apps, schema_editor):
    Workspace = apps.get_model('football', 'Workspace')
    WorkspaceCompetitionContext = apps.get_model('football', 'WorkspaceCompetitionContext')
    for context in WorkspaceCompetitionContext.objects.select_related('workspace', 'team').all():
        if context.team_id:
            continue
        ws = context.workspace
        if ws and getattr(ws, 'primary_team_id', None):
            context.team_id = ws.primary_team_id
            context.save(update_fields=['team'])


def _backfill_snapshot_workspace(apps, schema_editor):
    WorkspaceCompetitionSnapshot = apps.get_model('football', 'WorkspaceCompetitionSnapshot')
    for snapshot in WorkspaceCompetitionSnapshot.objects.select_related('context', 'workspace').all():
        if snapshot.workspace_id:
            continue
        ctx = snapshot.context
        if ctx and getattr(ctx, 'workspace_id', None):
            snapshot.workspace_id = ctx.workspace_id
            snapshot.save(update_fields=['workspace'])


class Migration(migrations.Migration):
    dependencies = [
        ('football', '0052_bootstrap_workspace_team_access_defaults'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workspacecompetitioncontext',
            name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competition_contexts', to='football.workspace'),
        ),
        migrations.RunPython(_backfill_competition_context_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='workspacecompetitionsnapshot',
            name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competition_snapshots', to='football.workspace'),
        ),
        migrations.AlterField(
            model_name='workspacecompetitionsnapshot',
            name='context',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='snapshot', to='football.workspacecompetitioncontext'),
        ),
        migrations.RunPython(_backfill_snapshot_workspace, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='workspacecompetitioncontext',
            constraint=models.UniqueConstraint(fields=('workspace', 'team'), condition=Q(team__isnull=False), name='uniq_workspace_team_competition_context'),
        ),
    ]
