from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_historical_report_archives(apps, schema_editor):
    PlayerStatistic = apps.get_model('football', 'PlayerStatistic')
    PlayerMatchReportArchive = apps.get_model('football', 'PlayerMatchReportArchive')
    rows = []
    ratings = (
        PlayerStatistic.objects.filter(
            match__isnull=False,
            match__is_closed=True,
            name='rating',
            context='auto-rating',
        )
        .values('player_id', 'match_id', 'value')
        .iterator(chunk_size=500)
    )
    for rating in ratings:
        rows.append(
            PlayerMatchReportArchive(
                player_id=rating['player_id'],
                match_id=rating['match_id'],
                version=1,
                status='pending',
                rating=rating['value'],
                snapshot={'historical_backfill': True},
                reason='historical_backfill',
            )
        )
        if len(rows) >= 500:
            PlayerMatchReportArchive.objects.bulk_create(rows, ignore_conflicts=True)
            rows = []
    if rows:
        PlayerMatchReportArchive.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ('football', '0230_workspaceteam_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerMatchReportArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveSmallIntegerField(default=1)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('ready', 'Listo'), ('error', 'Error')], db_index=True, default='pending', max_length=16)),
                ('rating', models.FloatField(blank=True, null=True)),
                ('minutes', models.PositiveSmallIntegerField(default=0)),
                ('snapshot', models.JSONField(blank=True, default=dict)),
                ('pdf', models.FileField(blank=True, null=True, upload_to='player-match-reports/')),
                ('reason', models.CharField(blank=True, max_length=120)),
                ('error_message', models.CharField(blank=True, max_length=240)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_player_match_reports', to=settings.AUTH_USER_MODEL)),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_report_archives', to='football.match')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_report_archives', to='football.player')),
            ],
            options={'ordering': ['-version', '-generated_at', '-id']},
        ),
        migrations.AddConstraint(
            model_name='playermatchreportarchive',
            constraint=models.UniqueConstraint(fields=('player', 'match', 'version'), name='uniq_player_match_report_version'),
        ),
        migrations.AddIndex(
            model_name='playermatchreportarchive',
            index=models.Index(fields=['player', 'match', '-version'], name='pmra_player_match_ver_idx'),
        ),
        migrations.AddIndex(
            model_name='playermatchreportarchive',
            index=models.Index(fields=['status', 'generated_at'], name='pmra_status_created_idx'),
        ),
        migrations.RunPython(seed_historical_report_archives, migrations.RunPython.noop),
    ]
