from django.db import migrations


def deactivate_discarded_linked_players(apps, schema_editor):
    """Backfill: los jugadores enlazados a un ojeado DESCARTADO que seguían activos se desactivan,
    para que dejen de aparecer en home / pizarra / convocatoria. Idempotente. En adelante, esto lo
    mantiene ScoutingTarget._sync_linked_player_active en el guardado del ojeo."""
    ScoutingTarget = apps.get_model('football', 'ScoutingTarget')
    Player = apps.get_model('football', 'Player')
    player_ids = set(
        ScoutingTarget.objects.filter(status='discarded', player__isnull=False)
        .values_list('player_id', flat=True)
    )
    if player_ids:
        Player.objects.filter(id__in=player_ids, is_active=True).update(is_active=False)


def noop(apps, schema_editor):
    # No se puede saber con certeza qué fichas reactivar; la reversión es un no-op deliberado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0184_player_hair_color_player_skin_grade'),
    ]

    operations = [
        migrations.RunPython(deactivate_discarded_linked_players, noop),
    ]
