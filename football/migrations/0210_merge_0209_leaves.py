from django.db import migrations


class Migration(migrations.Migration):
    """Merge de las dos migraciones 0209 en paralelo (creadas por sesiones distintas sobre 0208):
    0209_backfill_trial_squad_players y 0209_close_open_injuries_benagalbon_four. Sin este merge,
    `migrate` falla con 'multiple leaf nodes' y bloquea TODOS los deploys.
    """

    dependencies = [
        ('football', '0209_backfill_trial_squad_players'),
        ('football', '0209_close_open_injuries_benagalbon_four'),
    ]

    operations = []
