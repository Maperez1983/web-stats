from django.db import migrations


def normalize_positions(apps, schema_editor):
    """Normaliza las posiciones YA guardadas de todos los jugadores al valor
    canónico del sistema (POR, DFC, MC, ...), para que listado, dashboard e
    imagen sean consistentes. Los importados en bloque nunca pasaron por save()."""
    try:
        from football.normalization import normalize_position_value
    except Exception:
        return
    Player = apps.get_model("football", "Player")
    fields = ("position", "preferred_position", "previous_season_position")
    for player in Player.objects.all().iterator():
        changed = []
        for field in fields:
            current = getattr(player, field, "") or ""
            if not current:
                continue
            normalized = normalize_position_value(current)
            if normalized != current:
                setattr(player, field, normalized)
                changed.append(field)
        if changed:
            player.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0152_player_skin_tone"),
    ]

    operations = [
        migrations.RunPython(normalize_positions, migrations.RunPython.noop),
    ]
