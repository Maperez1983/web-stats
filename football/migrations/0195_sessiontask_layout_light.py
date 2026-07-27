from django.db import migrations, models


def backfill_light(apps, schema_editor):
    """Rellena task_layout_light = tactical_layout SIN el canvas pesado (tokens/timeline/
    meta.graphic_editor/meta.original_version) para las tareas ya existentes. One-time."""
    SessionTask = apps.get_model("football", "SessionTask")
    for task in SessionTask.objects.all().iterator(chunk_size=50):
        try:
            lay = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
            if not isinstance(lay, dict):
                task.task_layout_light = {}
            else:
                light = {k: v for k, v in lay.items() if k not in ("tokens", "timeline")}
                m = light.get("meta")
                if isinstance(m, dict):
                    light["meta"] = {k: v for k, v in m.items() if k not in ("graphic_editor", "original_version")}
                task.task_layout_light = light
            task.save(update_fields=["task_layout_light"])
        except Exception:
            continue


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0194_cleanup_legacy_memberships"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessiontask",
            name="task_layout_light",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_light, migrations.RunPython.noop),
    ]
