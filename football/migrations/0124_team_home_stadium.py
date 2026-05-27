from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0123_alter_sessiontask_objective_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='home_stadium',
            field=models.CharField(blank=True, help_text='Campo/estadio habitual del equipo', max_length=200),
        ),
    ]
