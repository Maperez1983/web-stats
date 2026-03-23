from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0025_userinvitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessiontask',
            name='task_pdf',
            field=models.FileField(blank=True, null=True, upload_to='session-tasks-pdf/'),
        ),
    ]
