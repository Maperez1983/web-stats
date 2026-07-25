# Fase 2 · Modelo teórico: columnas queryables de metodología en SessionTask.
# Añade columnas derivadas de tactical_layout['meta'] y rellena (backfill) las tareas
# existentes. La lógica de derivación se inlinea aquí para que la migración quede congelada
# (no depende de cambios futuros en football.task_choices).

from django.db import migrations, models


def _col_str(value, limit):
    try:
        s = str(value).strip() if value is not None else ""
    except Exception:
        s = ""
    return s[:limit]


def _derive(tactical_layout):
    meta = {}
    try:
        if isinstance(tactical_layout, dict):
            m = tactical_layout.get("meta")
            if isinstance(m, dict):
                meta = m
    except Exception:
        meta = {}
    return {
        "game_moment": _col_str(meta.get("game_moment"), 40),
        "principle": _col_str(meta.get("principle"), 160),
        "subprinciple": _col_str(meta.get("subprinciple"), 200),
        "structure_periodization": _col_str(meta.get("dominant_structure"), 40),
        "game_situation": _col_str(meta.get("structure"), 40),
        "content_domain": _col_str(meta.get("content_domain"), 30),
        "age_group": _col_str(meta.get("age_group"), 80),
    }


def backfill_columns(apps, schema_editor):
    SessionTask = apps.get_model("football", "SessionTask")
    fields = [
        "game_moment", "principle", "subprinciple", "structure_periodization",
        "game_situation", "content_domain", "age_group",
    ]
    qs = SessionTask.objects.all().only("id", "tactical_layout", *fields)
    for task in qs.iterator(chunk_size=500):
        try:
            cols = _derive(task.tactical_layout)
        except Exception:
            continue
        if any(getattr(task, k, "") != v for k, v in cols.items()):
            SessionTask.objects.filter(pk=task.pk).update(**cols)


def noop_reverse(apps, schema_editor):
    # Las columnas se eliminan con el AddField inverso; no hay que revertir datos.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0173_backfill_club_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessiontask',
            name='age_group',
            field=models.CharField(blank=True, db_index=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='content_domain',
            field=models.CharField(blank=True, db_index=True, default='', help_text='Contenido dominante: táctico/técnico/físico/psicológico', max_length=30),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='game_moment',
            field=models.CharField(blank=True, db_index=True, default='', help_text='Momento del juego (derivado del JSON)', max_length=40),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='game_situation',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='principle',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='structure_periodization',
            field=models.CharField(blank=True, db_index=True, default='', help_text='Estructura (periodización táctica)', max_length=40),
        ),
        migrations.AddField(
            model_name='sessiontask',
            name='subprinciple',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.RunPython(backfill_columns, noop_reverse),
    ]
