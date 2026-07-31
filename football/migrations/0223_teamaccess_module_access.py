from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0222_consolidar_bibliotecas_tareas"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspaceteamaccess",
            name="module_access",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
