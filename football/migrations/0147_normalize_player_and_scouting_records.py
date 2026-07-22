from django.db import migrations


def forwards(apps, schema_editor):
    from football.normalization import normalize_player_record, normalize_scouting_target_record

    db_alias = schema_editor.connection.alias
    Player = apps.get_model('football', 'Player')
    ScoutingTarget = apps.get_model('football', 'ScoutingTarget')

    for player in Player.objects.using(db_alias).all().iterator():
        changed_fields = normalize_player_record(player)
        if changed_fields:
            player.save(using=db_alias, update_fields=changed_fields)

    for target in ScoutingTarget.objects.using(db_alias).all().iterator():
        changed_fields = normalize_scouting_target_record(target)
        if changed_fields:
            target.save(using=db_alias, update_fields=changed_fields)


def backwards(apps, schema_editor):
    # Intentionally no-op: this migration only normalizes human-readable data.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0146_rename_svtok_prefix_active_idx_football_se_token_p_0068e2_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
