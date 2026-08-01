from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0144_serviceaccesstoken'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SessionTaskExportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('pdf_club', 'PDF Club'), ('pdf_uefa', 'PDF UEFA'), ('preview_png', 'Preview PNG'), ('sequence_gif', 'Secuencia GIF'), ('sequence_mp4', 'Secuencia MP4'), ('board_3d', 'Pizarra 3D'), ('canva', 'Canva / PPT')], default='pdf_club', max_length=40)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('running', 'En progreso'), ('done', 'Completado'), ('error', 'Error'), ('canceled', 'Cancelado')], db_index=True, default='pending', max_length=20)),
                ('progress', models.PositiveIntegerField(default=0)),
                ('message', models.CharField(blank=True, max_length=220)),
                ('error', models.TextField(blank=True)),
                ('cancel_requested', models.BooleanField(default=False)),
                ('result_url', models.CharField(blank=True, max_length=500)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='session_task_export_jobs', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_jobs', to='football.sessiontask')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_task_export_jobs', to='football.team')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='sessiontaskexportjob',
            index=models.Index(fields=['team', 'task', '-created_at'], name='football_ses_team_id_0a15af_idx'),
        ),
        migrations.AddIndex(
            model_name='sessiontaskexportjob',
            index=models.Index(fields=['team', 'status', '-created_at'], name='football_ses_team_id_d420f3_idx'),
        ),
        migrations.AddIndex(
            model_name='sessiontaskexportjob',
            index=models.Index(fields=['status', '-created_at'], name='football_ses_status_61b66b_idx'),
        ),
    ]
