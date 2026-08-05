from django.db import migrations


def indexar_lo_que_falta(apps, schema_editor):
    """Mete en el indice del recomendador las tareas de biblioteca que no estaban.

    El recomendador tiene dos caminos: el indice (rapido) y una consulta directa de reserva
    que SOLO se usa si el indice no devuelve nada. Con la biblioteca ya indexada, cualquier
    tarea que naciera sin indexar quedaba invisible para siempre: es lo que pasaba con las 22
    del libro, que se ven en la biblioteca pero el recomendador no las propone jamas.
    """
    SessionTask = apps.get_model('football', 'SessionTask')
    AiTrainerTaskIndex = apps.get_model('football', 'AiTrainerTaskIndex')
    try:
        from football.ai_trainer import ai_trainer_tokenize, normalize_ai_trainer_text
        from football.library_repositories import LIBRARY_MICROCYCLE_MARKER
    except Exception:
        return

    from django.db.models import Q

    ya_indexadas = set(AiTrainerTaskIndex.objects.values_list('task_id', flat=True))
    pendientes = (
        SessionTask.objects.select_related('session__microcycle')
        .filter(deleted_at__isnull=True)
        .filter(
            Q(session__microcycle__notes__icontains=LIBRARY_MICROCYCLE_MARKER)
            | Q(session__microcycle__title__istartswith='Biblioteca ')
        )
        .exclude(id__in=ya_indexadas)
        .order_by('id')
    )

    hechas = 0
    for tarea in pendientes.iterator(chunk_size=200):
        equipo = getattr(getattr(getattr(tarea, 'session', None), 'microcycle', None), 'team', None)
        if equipo is None:
            continue
        trozos = [
            str(getattr(tarea, 'title', '') or ''),
            str(getattr(tarea, 'objective', '') or ''),
            str(getattr(tarea, 'coaching_points', '') or ''),
            str(getattr(tarea, 'confrontation_rules', '') or ''),
        ]
        contenido = ' '.join([t for t in trozos if t.strip()]).strip()[:20000]
        if not contenido:
            continue
        contenido_norm = normalize_ai_trainer_text(contenido)[:20000]
        AiTrainerTaskIndex.objects.update_or_create(
            task=tarea,
            defaults={
                'team_id': equipo.id,
                'repository': '',
                'content': contenido,
                'content_norm': contenido_norm,
                'tokens': ai_trainer_tokenize(contenido_norm, limit=128),
            },
        )
        hechas += 1
    if hechas:
        print(f'  tareas de biblioteca indexadas para el recomendador: {hechas}')


def atras(apps, schema_editor):
    """No se borra nada: quitar filas del indice solo empeoraria las recomendaciones."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0242_sessiontask_task_family'),
    ]

    operations = [
        migrations.RunPython(indexar_lo_que_falta, atras),
    ]
