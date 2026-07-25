from django.db import migrations


def backfill_categories(apps, schema_editor):
    """Crea las `ClubCategory` desde los textos existentes (Team.category y
    Player.transferred_to_category) y enlaza los FKs, deduplicando por (club, name_key).
    Aditivo: no toca los campos de texto. Usa la MISMA normalización que el runtime."""
    from football.models import normalize_team_name_key

    Team = apps.get_model('football', 'Team')
    Player = apps.get_model('football', 'Player')
    ClubCategory = apps.get_model('football', 'ClubCategory')

    cache = {}

    def get_or_create_cat(club_id, name):
        key = normalize_team_name_key(name)
        if not club_id or not key:
            return None
        ck = (club_id, key)
        if ck in cache:
            return cache[ck]
        cat = ClubCategory.objects.filter(club_id=club_id, name_key=key).first()
        if cat is None:
            cat = ClubCategory.objects.create(
                club_id=club_id, name=str(name or '').strip()[:60], name_key=key
            )
        cache[ck] = cat
        return cat

    for team in Team.objects.exclude(category='').filter(club__isnull=False).only(
        'id', 'category', 'club_id', 'category_ref_id'
    ):
        if team.category_ref_id is None:
            cat = get_or_create_cat(team.club_id, team.category)
            if cat is not None:
                Team.objects.filter(pk=team.pk).update(category_ref=cat)

    for player in Player.objects.exclude(transferred_to_category='').filter(
        transferred_to_club__isnull=False
    ).only('id', 'transferred_to_category', 'transferred_to_club_id', 'transferred_to_category_ref_id'):
        if player.transferred_to_category_ref_id is None:
            cat = get_or_create_cat(player.transferred_to_club_id, player.transferred_to_category)
            if cat is not None:
                Player.objects.filter(pk=player.pk).update(transferred_to_category_ref=cat)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0172_clubcategory_player_transferred_to_category_ref_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_categories, migrations.RunPython.noop),
    ]
