from django.db import migrations


def backfill_kind(apps, schema_editor):
    """Rellena MatchEvent.kind del histórico: usa raw_data['kind'] si existe (Fase 1),
    y si no, deriva el tipo canónico del texto. No falla nunca; deja '' si no clasifica."""
    from football.event_taxonomy import CANONICAL_EVENT_KINDS, canonical_event_kind

    MatchEvent = apps.get_model("football", "MatchEvent")
    to_update = []
    qs = MatchEvent.objects.all().only(
        "id", "event_type", "result", "zone", "observation", "raw_data", "kind"
    )
    for ev in qs:
        raw = ev.raw_data if isinstance(ev.raw_data, dict) else {}
        stored = str(raw.get("kind") or "").strip().lower()
        kind = stored if stored in CANONICAL_EVENT_KINDS else canonical_event_kind(
            ev.event_type, ev.result, ev.zone, ev.observation
        )
        if kind and ev.kind != kind:
            ev.kind = kind
            to_update.append(ev)
    for i in range(0, len(to_update), 2000):
        MatchEvent.objects.bulk_update(to_update[i : i + 2000], ["kind"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0206_matchevent_kind"),
    ]
    operations = [
        migrations.RunPython(backfill_kind, noop),
    ]
