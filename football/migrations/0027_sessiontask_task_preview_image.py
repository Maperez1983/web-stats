from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0026_sessiontask_task_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessiontask',
            name='task_preview_image',
            field=models.ImageField(blank=True, null=True, upload_to='session-tasks-preview/'),
        ),
    ]
