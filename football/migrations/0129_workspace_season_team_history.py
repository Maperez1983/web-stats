from django.db import migrations, models
import django.db.models.deletion


def seed_season_history(apps, schema_editor):
    Workspace = apps.get_model('football', 'Workspace')
    WorkspaceTeam = apps.get_model('football', 'WorkspaceTeam')
    WorkspaceSeasonTeam = apps.get_model('football', 'WorkspaceSeasonTeam')
    WorkspaceSeasonPlayer = apps.get_model('football', 'WorkspaceSeasonPlayer')
    Player = apps.get_model('football', 'Player')

    for workspace in Workspace.objects.filter(active_season__isnull=False).only('id', 'active_season_id'):
        season_id = workspace.active_season_id
        team_ids = list(
            WorkspaceTeam.objects
            .filter(workspace_id=workspace.id)
            .values_list('team_id', flat=True)
        )
        for team_id in team_ids:
            if not team_id:
                continue
            WorkspaceSeasonTeam.objects.get_or_create(
                season_id=season_id,
                team_id=team_id,
                defaults={'status': 'active', 'is_active': True},
            )

            player_ids = list(Player.objects.filter(team_id=team_id).values_list('id', 'is_active'))
            existing = set(
                WorkspaceSeasonPlayer.objects
                .filter(season_id=season_id, player_id__in=[pid for pid, _active in player_ids])
                .values_list('player_id', flat=True)
            )
            missing = [
                WorkspaceSeasonPlayer(
                    season_id=season_id,
                    player_id=pid,
                    is_confirmed=False,
                    status='pending' if is_active else 'inactive',
                )
                for pid, is_active in player_ids
                if pid and pid not in existing
            ]
            if missing:
                WorkspaceSeasonPlayer.objects.bulk_create(missing, ignore_conflicts=True)

    for membership in WorkspaceSeasonPlayer.objects.select_related('player').only('id', 'is_confirmed', 'status', 'player__is_active'):
        desired = 'confirmed' if membership.is_confirmed else ('pending' if membership.player.is_active else 'inactive')
        if membership.status != desired:
            membership.status = desired
            membership.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0128_playerseasonreport_decimal_ratings'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkspaceSeasonTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Activo en temporada'), ('archived', 'Archivado'), ('not_continuing', 'No continúa')], db_index=True, default='active', max_length=24)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('season', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='season_teams', to='football.workspaceseason')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='season_memberships', to='football.team')),
            ],
            options={
                'verbose_name': 'Equipo de temporada (club)',
                'verbose_name_plural': 'Equipos de temporada (club)',
                'ordering': ['-is_active', 'team__name', 'id'],
                'unique_together': {('season', 'team')},
            },
        ),
        migrations.AddField(
            model_name='workspaceseasonplayer',
            name='left_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='workspaceseasonplayer',
            name='status',
            field=models.CharField(choices=[('pending', 'Pendiente'), ('confirmed', 'Confirmado'), ('inactive', 'Inactivo'), ('left', 'No continúa')], db_index=True, default='pending', max_length=24),
        ),
        migrations.AddField(
            model_name='workspaceseasonplayer',
            name='status_notes',
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AlterModelOptions(
            name='workspaceseasonplayer',
            options={'ordering': ['-is_confirmed', 'status', 'player__name', 'id'], 'verbose_name': 'Jugador de temporada (club)', 'verbose_name_plural': 'Jugadores de temporada (club)'},
        ),
        migrations.AlterField(
            model_name='workspacecompetitioncontext',
            name='provider',
            field=models.CharField(choices=[('manual', 'Manual / base local'), ('rfaf', 'RFAF'), ('universo_rfaf', 'Universo RFAF'), ('lapreferente', 'La Preferente')], default='manual', max_length=32),
        ),
        migrations.AddIndex(
            model_name='workspaceseasonteam',
            index=models.Index(fields=['season', 'is_active'], name='wst_season_active_idx'),
        ),
        migrations.AddIndex(
            model_name='workspaceseasonteam',
            index=models.Index(fields=['team', '-created_at'], name='wst_team_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workspaceseasonplayer',
            index=models.Index(fields=['season', 'status'], name='wsp_season_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workspaceseasonplayer',
            index=models.Index(fields=['player', '-created_at'], name='wsp_player_created_idx'),
        ),
        migrations.RunPython(seed_season_history, migrations.RunPython.noop),
    ]
