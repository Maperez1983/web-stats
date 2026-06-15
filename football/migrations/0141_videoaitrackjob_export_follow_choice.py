from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0140_videoaigamecalibration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='videoaitrackjob',
            name='action',
            field=models.CharField(
                choices=[
                    ('reid', 'ReID'),
                    ('batch', 'Batch'),
                    ('train', 'Entrenamiento'),
                    ('detect_actions', 'Detección de acciones'),
                    ('train_actions', 'Entrenamiento de acciones'),
                    ('export_follow', 'Exportar seguimiento'),
                ],
                default='reid',
                max_length=24,
            ),
        ),
    ]
