from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0009_convocationrecord_match_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessiontask',
            name='coaching_points',
            field=models.TextField(blank=True, help_text='Consignas clave para ejecutar la tarea'),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='confrontation_rules',
            field=models.TextField(blank=True, help_text='Reglas de confrontación y puntuación'),
        ),
    ]
