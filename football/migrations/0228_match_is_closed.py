from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0227_parte_medico_publicado"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="is_closed",
            field=models.BooleanField(
                default=False,
                help_text="Marca si el partido ya se cerro y no debe seguir apareciendo como pendiente en convocatoria.",
            ),
        ),
    ]
