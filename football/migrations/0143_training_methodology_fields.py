from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0142_rivalvideo_ingest_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingmicrocycle',
            name='cycle_type',
            field=models.CharField(
                choices=[
                    ('standard', 'Competición'),
                    ('double_match', 'Doble partido'),
                    ('load', 'Carga'),
                    ('taper', 'Afinar'),
                    ('regen', 'Regenerativo'),
                    ('preseason', 'Pretemporada'),
                ],
                default='standard',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='trainingmicrocycle',
            name='game_model_focus',
            field=models.CharField(blank=True, default='', max_length=180),
        ),
        migrations.AddField(
            model_name='trainingmicrocycle',
            name='game_moment',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='trainingmicrocycle',
            name='principle',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='trainingmicrocycle',
            name='subprinciple',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.AddField(
            model_name='trainingsession',
            name='dominant_load',
            field=models.CharField(
                blank=True,
                choices=[
                    ('recovery', 'Recuperación'),
                    ('tension', 'Tensión'),
                    ('duration', 'Duración'),
                    ('speed', 'Velocidad'),
                    ('activation', 'Activación'),
                    ('mixed', 'Mixta'),
                ],
                default='',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='trainingsession',
            name='game_moment',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='trainingsession',
            name='md_day',
            field=models.CharField(
                blank=True,
                choices=[
                    ('md_plus_1', 'MD+1 Recuperación'),
                    ('md_plus_2', 'MD+2 Descanso / compensatorio'),
                    ('md_minus_4', 'MD-4 Tensión'),
                    ('md_minus_3', 'MD-3 Duración'),
                    ('md_minus_2', 'MD-2 Velocidad'),
                    ('md_minus_1', 'MD-1 Activación'),
                    ('md', 'MD Partido'),
                    ('custom', 'Personalizado'),
                ],
                default='',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='trainingsession',
            name='principle',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='trainingsession',
            name='subprinciple',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.AddField(
            model_name='trainingsessionreview',
            name='cognitive_load',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Carga cognitiva percibida 1-10', null=True),
        ),
        migrations.AddField(
            model_name='trainingsessionreview',
            name='emotional_load',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Carga emocional percibida 1-10', null=True),
        ),
        migrations.AddField(
            model_name='trainingsessionreview',
            name='execution_score',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Ejecución del objetivo 1-10', null=True),
        ),
        migrations.AddField(
            model_name='trainingsessionreview',
            name='physical_load',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Carga física percibida 1-10', null=True),
        ),
    ]
