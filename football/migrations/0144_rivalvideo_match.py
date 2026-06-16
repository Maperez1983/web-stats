from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0143_training_methodology_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='rivalvideo',
            name='match',
            field=models.ForeignKey(
                blank=True,
                help_text='Partido al que pertenece este vídeo de análisis.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='analysis_videos',
                to='football.match',
            ),
        ),
        migrations.AddIndex(
            model_name='rivalvideo',
            index=models.Index(fields=['match', '-created_at'], name='rivalvideo_match_created_idx'),
        ),
    ]
