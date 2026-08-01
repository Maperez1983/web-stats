from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0226_comunicacion_publicada"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="playerinjuryrecord",
            name="published_to_player",
            field=models.BooleanField(default=False, help_text="Visible en el portal del jugador."),
        ),
        migrations.AddField(
            model_name="playerinjuryrecord",
            name="published_to_player_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="playerinjuryrecord",
            name="published_to_player_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="published_player_injuries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
