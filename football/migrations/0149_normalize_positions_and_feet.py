from django.db import migrations


def normalize_existing_choices(apps, schema_editor):
    Player = apps.get_model("football", "Player")
    ScoutingTarget = apps.get_model("football", "ScoutingTarget")

    try:
        from football.normalization import normalize_player_record, normalize_scouting_target_record
    except Exception:
        normalize_player_record = None
        normalize_scouting_target_record = None

    if normalize_player_record is not None:
        for player in Player.objects.all().iterator():
            changed = normalize_player_record(player)
            if changed:
                player.save(update_fields=changed)

    if normalize_scouting_target_record is not None:
        for target in ScoutingTarget.objects.all().iterator():
            changed = normalize_scouting_target_record(target)
            if changed:
                target.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0148_injury_detail_and_choice_lists"),
    ]

    operations = [
        migrations.RunPython(normalize_existing_choices, migrations.RunPython.noop),
    ]
