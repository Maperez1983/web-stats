from django.db import migrations


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def backfill_player_identity(apps, schema_editor):
    """
    Crea una PlayerIdentity por cada Player existente, reutilizando (deduplicando) la
    identidad SOLO cuando coincide una clave FUERTE:
      1) misma URL de perfil externo no vacía (preferente/transfermarkt/besoccer), o
      2) mismo nombre normalizado + misma fecha de nacimiento (ambos presentes).

    Es deliberadamente conservador: si no hay clave fuerte, cada Player recibe su propia
    identidad (nunca fusiona homónimos sin fecha de nacimiento).
    """
    Player = apps.get_model("football", "Player")
    PlayerIdentity = apps.get_model("football", "PlayerIdentity")

    by_url = {}       # url -> identity_id
    by_name_dob = {}  # (norm_name, birth_date) -> identity_id

    qs = Player.objects.all().order_by("id").only(
        "id", "name", "full_name", "birth_date", "identity_id",
        "preferente_profile_url", "transfermarkt_url", "besoccer_url",
    )
    for player in qs.iterator():
        if getattr(player, "identity_id", None):
            continue
        urls = [
            str(getattr(player, "preferente_profile_url", "") or "").strip(),
            str(getattr(player, "transfermarkt_url", "") or "").strip(),
            str(getattr(player, "besoccer_url", "") or "").strip(),
        ]
        urls = [u for u in urls if u]

        identity_id = None
        for url in urls:
            if url in by_url:
                identity_id = by_url[url]
                break

        norm_name = _norm(player.full_name or player.name)
        dob = player.birth_date
        name_key = (norm_name, dob) if (norm_name and dob is not None) else None
        if identity_id is None and name_key is not None and name_key in by_name_dob:
            identity_id = by_name_dob[name_key]

        if identity_id is None:
            identity = PlayerIdentity.objects.create(
                full_name=str(player.full_name or player.name or "")[:180],
                display_name=str(player.name or "")[:120],
                birth_date=dob,
                preferente_profile_url=str(getattr(player, "preferente_profile_url", "") or "")[:300],
                transfermarkt_url=str(getattr(player, "transfermarkt_url", "") or "")[:300],
                besoccer_url=str(getattr(player, "besoccer_url", "") or "")[:300],
            )
            identity_id = identity.id

        for url in urls:
            by_url.setdefault(url, identity_id)
        if name_key is not None:
            by_name_dob.setdefault(name_key, identity_id)

        player.identity_id = identity_id
        player.save(update_fields=["identity"])


def reverse_backfill(apps, schema_editor):
    # Desvincula (no borra identidades para no perder datos si se re-aplica).
    Player = apps.get_model("football", "Player")
    Player.objects.exclude(identity__isnull=True).update(identity=None)


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0162_playeridentity_player_identity"),
    ]

    operations = [
        migrations.RunPython(backfill_player_identity, reverse_backfill),
    ]
