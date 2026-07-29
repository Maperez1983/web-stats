from django.db import migrations


def close_open_injuries(apps, schema_editor):
    """Limpieza puntual: cierra las lesiones ABIERTAS (is_active=True) de Juanmi, Andrews, Victor y
    Cristian del equipo Benagalbon. Arrastraban lesiones antiguas SIN fecha de alta (is_active=True,
    return_date nulo) que los mantenian "lesionados" en todas las pizarras pese a estar recuperados.
    Scope estrecho (equipo + nombres) -> no-op en cualquier otra base de datos.
    """
    PlayerInjuryRecord = apps.get_model('football', 'PlayerInjuryRecord')
    PlayerInjuryRecord.objects.filter(
        player__team__name__icontains='benagalb',
        player__name__in=['Juanmi', 'Andrews', 'Victor', 'Cristian'],
        is_active=True,
    ).update(is_active=False, is_recovered=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0208_discharge_stuck_injuries'),
    ]

    operations = [
        migrations.RunPython(close_open_injuries, noop),
    ]
