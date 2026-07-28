"""Infiere Match.stats_source de los partidos existentes (fuente única de datos).

Regla (por prioridad):
- Tiene eventos de registro en vivo (source_file="registro-acciones") -> 'live'.
- Tiene eventos manuales (source_file in {"manual-bulk", "admin-manual"})   -> 'manual'.
- Tiene marcador (home_score o away_score no nulo)                          -> 'result_only'.
- En otro caso                                                              -> '' (sin datos).

Idempotente y reversible (la reversa deja stats_source vacío). No toca eventos ni marcadores.
"""

from django.db import migrations


LIVE_SOURCES = ("registro-acciones",)
MANUAL_SOURCES = ("manual-bulk", "admin-manual")


def infer(apps, schema_editor):
    Match = apps.get_model("football", "Match")
    MatchEvent = apps.get_model("football", "MatchEvent")

    for match in Match.objects.all().iterator():
        has_live = MatchEvent.objects.filter(match=match, source_file__in=LIVE_SOURCES).exists()
        if has_live:
            source = "live"
        elif MatchEvent.objects.filter(match=match, source_file__in=MANUAL_SOURCES).exists():
            source = "manual"
        elif match.home_score is not None or match.away_score is not None:
            source = "result_only"
        else:
            source = ""
        if match.stats_source != source:
            match.stats_source = source
            match.save(update_fields=["stats_source"])


def clear(apps, schema_editor):
    Match = apps.get_model("football", "Match")
    Match.objects.exclude(stats_source="").update(stats_source="")


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0199_match_stats_source"),
    ]

    operations = [
        migrations.RunPython(infer, clear),
    ]
