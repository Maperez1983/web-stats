from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0016_rivalvideo'),
    ]

    operations = [
        migrations.AddField(
            model_name='convocationrecord',
            name='lineup_data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
