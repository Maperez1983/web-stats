from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0223_teamaccess_module_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="contact_email",
            field=models.EmailField(blank=True, help_text="Email al que llega la invitación al portal.", max_length=254),
        ),
        migrations.AddField(
            model_name="player",
            name="contact_name",
            field=models.CharField(blank=True, help_text="De quién es ese email (el jugador, su padre, su madre…).", max_length=160),
        ),
        migrations.AddField(
            model_name="player",
            name="contact_is_guardian",
            field=models.BooleanField(default=False, help_text="El contacto es un familiar o tutor, no el propio jugador."),
        ),
    ]
