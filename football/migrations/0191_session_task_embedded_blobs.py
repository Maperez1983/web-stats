from django.db import migrations, models
from django.db.models import Q


def move_blobs_out(apps, schema_editor):
    """Mueve los blobs base64 (preview 2D / portada IA) de tactical_layout.meta a las
    columnas dedicadas, para que los listados no tengan que leerlos. One-time."""
    SessionTask = apps.get_model("football", "SessionTask")
    qs = SessionTask.objects.filter(
        Q(tactical_layout__meta__has_key="preview_data_embedded_v1")
        | Q(tactical_layout__meta__has_key="cover_image_embedded_v1")
    )
    for task in qs.iterator(chunk_size=50):
        try:
            layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
            meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else None
            if not isinstance(meta, dict):
                continue
            changed = False
            pv = meta.pop("preview_data_embedded_v1", None)
            if isinstance(pv, str) and pv.strip():
                task.preview_data_b64 = pv
                changed = True
            cv = meta.pop("cover_image_embedded_v1", None)
            if isinstance(cv, str) and cv.strip():
                task.cover_data_b64 = cv
                task.cover_present = True
                changed = True
            ov = meta.get("original_version")
            if isinstance(ov, dict):
                if ov.pop("preview_data_embedded_v1", None) is not None:
                    changed = True
                if ov.pop("cover_image_embedded_v1", None) is not None:
                    changed = True
            if changed:
                task.save(
                    update_fields=[
                        "tactical_layout",
                        "preview_data_b64",
                        "cover_data_b64",
                        "cover_present",
                    ]
                )
        except Exception:
            # No abortamos la migración por una fila mala; los lectores caen a meta de reserva.
            continue


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0190_rollover_benagalbon_2026_27"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessiontask",
            name="preview_data_b64",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="sessiontask",
            name="cover_data_b64",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="sessiontask",
            name="cover_present",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Flag barato para listados: hay portada IA embebida",
            ),
        ),
        migrations.RunPython(move_blobs_out, migrations.RunPython.noop),
    ]
