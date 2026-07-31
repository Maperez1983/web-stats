from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def marcar_convocatorias(apps, schema_editor):
    """
    Las de categoría `convocatoria` YA se veían en el portal (el filtro era por categoría).
    Se marcan como publicadas para que nadie pierda de vista lo que ya tenía; el resto
    (internas y médicas) nace sin publicar, que es justo el cambio que se busca.
    """
    PlayerCommunication = apps.get_model("football", "PlayerCommunication")
    PlayerCommunication.objects.filter(category="convocatoria").update(published_to_player=True)


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0225_player_user_is_guardian"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="playercommunication",
            name="published_to_player",
            field=models.BooleanField(default=False, help_text="Visible en el portal del jugador."),
        ),
        migrations.AddField(
            model_name="playercommunication",
            name="published_to_player_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="playercommunication",
            name="published_to_player_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="published_player_communications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(marcar_convocatorias, migrations.RunPython.noop),
    ]
