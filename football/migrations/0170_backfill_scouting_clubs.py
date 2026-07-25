from django.db import migrations


def backfill_scouting_clubs(apps, schema_editor):
    """Enlaza los ojeos existentes al catálogo de clubes desde su texto (subject_team_name ->
    subject_club; discard_club -> signed_club), reutilizando el club por name_key sin duplicar.
    Usa la MISMA normalización que el runtime para que dedupliquen igual."""
    from football.models import normalize_team_name_key

    ScoutingTarget = apps.get_model('football', 'ScoutingTarget')
    Club = apps.get_model('football', 'Club')

    cache = {}

    def resolve(name):
        key = normalize_team_name_key(name)
        if not key:
            return None
        if key in cache:
            return cache[key]
        club = Club.objects.filter(name_key=key).first()
        if club is None:
            club = Club.objects.create(name=str(name or '').strip()[:150] or 'Club', name_key=key)
        cache[key] = club
        return club

    qs = ScoutingTarget.objects.all().only(
        'id', 'subject_team_name', 'discard_club', 'subject_club_id', 'signed_club_id'
    )
    for target in qs:
        updates = {}
        if target.subject_club_id is None and (target.subject_team_name or '').strip():
            club = resolve(target.subject_team_name)
            if club is not None:
                updates['subject_club'] = club
        if target.signed_club_id is None and (target.discard_club or '').strip():
            club = resolve(target.discard_club)
            if club is not None:
                updates['signed_club'] = club
        if updates:
            ScoutingTarget.objects.filter(pk=target.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0169_scoutingtarget_signed_club_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_scouting_clubs, migrations.RunPython.noop),
    ]
