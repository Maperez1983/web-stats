from __future__ import annotations

import logging

from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from football.bootstrap import ensure_bootstrap_admin_from_env
from football.models import SessionTask

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def ensure_bootstrap_admin(sender, **kwargs):
    if getattr(sender, 'name', '') != 'football':
        return
    ensure_bootstrap_admin_from_env()


@receiver(post_save, sender=SessionTask)
def aprender_de_la_tarea_puesta_en_sesion(sender, instance, created, **kwargs):
    """Cuando una tarea entra en una sesión de verdad, refuerza sus conceptos.

    Por señal y no en las vistas a propósito: hay DOCE puntos distintos que crean SessionTask
    (crear a mano, copiar de biblioteca, duplicar, importar PPTX, plantilla de microciclo…) y
    engancharlos uno a uno se rompería en cuanto apareciera el decimotercero.

    Solo al CREAR: editar una tarea diez veces no significa que te guste diez veces más.
    Nunca propaga una excepción: preferimos no aprender antes que impedir guardar una sesión.
    """
    # REINDEXAR SIEMPRE, tambien al editar: el indice solo se escribia al crear, en tres
    # sitios sueltos, asi que si reescribias el objetivo de una tarea el recomendador seguia
    # puntuando el texto viejo para siempre. Solo las de biblioteca, que son las candidatas.
    try:
        from football.ai_trainer import ai_trainer_index_task
        from football.library_repositories import is_library_microcycle

        microciclo = getattr(getattr(instance, 'session', None), 'microcycle', None)
        if microciclo is not None and is_library_microcycle(microciclo):
            ai_trainer_index_task(instance)
    except Exception:
        logger.debug('No se pudo reindexar la tarea %s', getattr(instance, 'id', None), exc_info=True)

    if not created:
        return
    try:
        from football.ai_trainer import aprender_de_tarea_usada

        aprender_de_tarea_usada(instance)
    except Exception:
        logger.debug('No se pudo aprender de la tarea %s', getattr(instance, 'id', None), exc_info=True)
    try:
        from football.ai_trainer import apuntar_uso_en_la_tarea_de_biblioteca

        apuntar_uso_en_la_tarea_de_biblioteca(instance)
    except Exception:
        logger.debug(
            'No se pudo apuntar el uso de la tarea %s', getattr(instance, 'id', None), exc_info=True
        )
