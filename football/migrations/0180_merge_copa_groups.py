from django.db import migrations


def merge_copa_groups(apps, schema_editor):
    """Fusión de un solo uso: los dos «Grupo 2 · COPA FED 3 ANDALUZA» (external_id 47051884 y
    48199749) son el MISMO grupo duplicado (solo hubo Copa 2025/2026, confirmado). Se filtra por
    name='Grupo 2' + esos external_id para NO tocar el «Grupo único» Prebenjamín, que comparte el
    id 48199749. Idempotente: si ya queda uno, no hace nada. Usa el `merge_groups` real (reasigna
    equipos/partidos/clasificación por relaciones inversas y borra el duplicado)."""
    from football.models import Group, merge_groups

    groups = list(
        Group.objects.filter(name="Grupo 2", external_id__in=["47051884", "48199749"]).order_by("id")
    )
    if len(groups) < 2:
        return

    def score(g):
        content = g.teams.count() + g.matches.count() + g.standings.count()
        return (content, 1 if g.external_id else 0, -g.id)

    keep = max(groups, key=score)
    for g in groups:
        if g.pk != keep.pk:
            merge_groups(keep, g)


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0179_playerobjective"),
    ]

    operations = [
        migrations.RunPython(merge_copa_groups, migrations.RunPython.noop),
    ]
