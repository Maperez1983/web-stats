from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0125_team_stadium_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='staff_captain',
            field=models.ForeignKey(
                blank=True,
                help_text='Capitán destacado por el staff al cerrar el registro de acciones.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='staff_captain_matches',
                to='football.player',
            ),
        ),
        migrations.AddField(
            model_name='match',
            name='staff_mvp',
            field=models.ForeignKey(
                blank=True,
                help_text='Mejor jugador elegido por el staff al cerrar el registro de acciones.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='staff_mvp_matches',
                to='football.player',
            ),
        ),
    ]
