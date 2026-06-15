from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('football', '0139_video_ai_tactical_knowledge'),
    ]

    operations = [
        migrations.CreateModel(
            name='VideoAiGameCalibration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attack_direction', models.CharField(choices=[('ltr', 'Izquierda a derecha'), ('rtl', 'Derecha a izquierda'), ('unknown', 'Desconocida')], default='unknown', max_length=12)),
                ('phase', models.CharField(blank=True, help_text='Parte o tramo: first_half, second_half, custom...', max_length=40)),
                ('field_points', models.JSONField(blank=True, default=dict, help_text='Puntos normalizados validados por el analista.')),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('confidence', models.FloatField(default=0)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='video_ai_game_calibrations', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='video_ai_game_calibrations', to='football.team')),
                ('video', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_game_calibrations', to='football.rivalvideo')),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
                'unique_together': {('team', 'video', 'phase')},
            },
        ),
        migrations.AddIndex(
            model_name='videoaigamecalibration',
            index=models.Index(fields=['team', 'video', '-updated_at'], name='football_vi_team_id_3a3056_idx'),
        ),
        migrations.AddIndex(
            model_name='videoaigamecalibration',
            index=models.Index(fields=['video', 'phase'], name='football_vi_video_i_b913e6_idx'),
        ),
    ]
