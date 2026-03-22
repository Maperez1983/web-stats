from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0018_player_manual_sanction_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='RivalAnalysisReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rival_name', models.CharField(max_length=180)),
                ('report_title', models.CharField(blank=True, max_length=180)),
                ('match_round', models.CharField(blank=True, max_length=80)),
                ('match_date', models.CharField(blank=True, max_length=60)),
                ('match_location', models.CharField(blank=True, max_length=180)),
                ('tactical_system', models.CharField(blank=True, help_text='Ej: 1-4-2-3-1', max_length=80)),
                ('attacking_patterns', models.TextField(blank=True, help_text='Cómo progresan, zonas, mecanismos')),
                ('defensive_patterns', models.TextField(blank=True, help_text='Altura bloque, presión, ajustes')),
                ('transitions', models.TextField(blank=True, help_text='Comportamiento en transición OF/DEF')),
                ('set_pieces_for', models.TextField(blank=True, help_text='ABP ofensivas del rival')),
                ('set_pieces_against', models.TextField(blank=True, help_text='ABP defensivas del rival')),
                ('key_players', models.TextField(blank=True, help_text='Jugadores determinantes y perfil')),
                ('weaknesses', models.TextField(blank=True, help_text='Puntos atacables')),
                ('opportunities', models.TextField(blank=True, help_text='Dónde hacer daño')),
                ('match_plan', models.TextField(blank=True, help_text='Plan de partido propuesto')),
                ('individual_tasks', models.TextField(blank=True, help_text='Tareas por línea/jugador')),
                ('alert_notes', models.TextField(blank=True, help_text='Alertas: sanciones, lesiones, riesgos')),
                ('confidence_level', models.PositiveSmallIntegerField(default=3, help_text='1-5')),
                ('status', models.CharField(choices=[('draft', 'Borrador'), ('ready', 'Listo para partido')], default='draft', max_length=16)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rival_team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analysis_reports_as_rival', to='football.team')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rival_analysis_reports', to='football.team')),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
            },
        ),
    ]
