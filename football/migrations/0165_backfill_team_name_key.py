import unicodedata

from django.db import migrations


def _norm_key(name):
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def backfill_team_name_key(apps, schema_editor):
    Team = apps.get_model("football", "Team")
    for team in Team.objects.all().only("id", "name", "name_key").iterator():
        key = _norm_key(team.name)
        if team.name_key != key:
            team.name_key = key
            team.save(update_fields=["name_key"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0164_team_name_key"),
    ]

    operations = [
        migrations.RunPython(backfill_team_name_key, noop),
    ]
