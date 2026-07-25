import unicodedata

from django.db import migrations


def _norm_key(name):
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def backfill_club(apps, schema_editor):
    """
    Agrupa los Team existentes en Club por name_key: todos los equipos con la misma clave de
    nombre (p. ej. las categorías de Benagalbón) quedan bajo un mismo Club. Los equipos sin
    clave reciben un club propio. Conservador: no fusiona nombres distintos.
    """
    Team = apps.get_model("football", "Team")
    Club = apps.get_model("football", "Club")

    key_to_club = {}
    for team in Team.objects.all().order_by("id").only("id", "name", "short_name", "club_id").iterator():
        if team.club_id:
            continue
        key = _norm_key(team.name)
        club_id = key_to_club.get(key) if key else None
        if club_id is None:
            club = Club.objects.create(
                name=str(team.name or "")[:150] or "Club",
                name_key=key,
                short_name=str(team.short_name or "")[:80],
            )
            club_id = club.id
            if key:
                key_to_club[key] = club_id
        team.club_id = club_id
        team.save(update_fields=["club"])


def reverse_backfill(apps, schema_editor):
    Team = apps.get_model("football", "Team")
    Team.objects.exclude(club__isnull=True).update(club=None)


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0166_club_team_club"),
    ]

    operations = [
        migrations.RunPython(backfill_club, reverse_backfill),
    ]
