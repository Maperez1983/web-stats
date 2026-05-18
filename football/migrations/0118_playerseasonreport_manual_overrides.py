from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0117_workspaceseasonphase"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerseasonreport",
            name="manual_overrides",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Overrides manuales (stats/partidos) para el PDF cuando faltan datos o hay inconsistencias.",
            ),
        ),
    ]

