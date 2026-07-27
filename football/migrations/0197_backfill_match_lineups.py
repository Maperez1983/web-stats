"""Backfill de MatchLineup desde ConvocationRecord.lineup_data existente.

Copia la alineación actual (starters/bench) de cada convocatoria que tenga partido asociado y
lineup_data con contenido, hacia el nuevo modelo MatchLineup (fuente de verdad propia). Idempotente
y reversible (la reversa borra los MatchLineup creados). No toca ConvocationRecord.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    ConvocationRecord = apps.get_model("football", "ConvocationRecord")
    MatchLineup = apps.get_model("football", "MatchLineup")

    qs = ConvocationRecord.objects.exclude(match__isnull=True).exclude(lineup_data={}).order_by("id")
    for record in qs.iterator():
        lineup = record.lineup_data
        if not isinstance(lineup, dict):
            continue
        if not (lineup.get("starters") or lineup.get("bench")):
            continue
        team_id = record.team_id
        match_id = record.match_id
        if not team_id or not match_id:
            continue
        # La convocatoria más reciente gana (qs ordenado por id asc → el último sobrescribe).
        MatchLineup.objects.update_or_create(
            team_id=team_id,
            match_id=match_id,
            defaults={"lineup_data": lineup},
        )


def unbackfill(apps, schema_editor):
    MatchLineup = apps.get_model("football", "MatchLineup")
    MatchLineup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0196_matchlineup"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
