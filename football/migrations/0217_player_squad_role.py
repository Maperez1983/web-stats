from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0216_player_traits'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='squad_role',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Rol de plantilla FIJADO manualmente (clave/titular/rotacion/promesa/suplente/prescindible). Vacío = automático.',
                max_length=16,
            ),
        ),
    ]
