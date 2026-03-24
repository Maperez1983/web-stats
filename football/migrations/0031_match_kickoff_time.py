from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0027_sessiontask_task_preview_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='kickoff_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
