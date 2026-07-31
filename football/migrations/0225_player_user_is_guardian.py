from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0224_player_contacto"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="user_is_guardian",
            field=models.BooleanField(default=False, help_text="La cuenta vinculada es de un familiar o tutor."),
        ),
    ]
