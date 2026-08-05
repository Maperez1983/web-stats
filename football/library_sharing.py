"""Una carpeta de la biblioteca es material del club, no de una categoría.

Las tareas importadas de un libro se guardan colgando del equipo principal (el senior), que es
quien tiene la biblioteca. Pero no son del senior: son del club. Desde que las listas filtran
por categoría, al cadete le desaparecían — y abrir una por su id daba "no encontrada".

La regla: si una tarea está archivada en una carpeta de cualquier equipo del MISMO espacio de
trabajo, se ve desde cualquier categoría de ese espacio. Fuera del espacio, no.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def equipos_del_espacio(workspace, team=None):
    """Ids de los equipos del club. El de referencia entra siempre, aunque falte el espacio."""
    from .models import WorkspaceTeam

    ids = set()
    if workspace is not None and getattr(workspace, "id", None):
        try:
            ids = {
                int(tid)
                for tid in WorkspaceTeam.objects.filter(workspace=workspace).values_list("team_id", flat=True)
                if tid
            }
        except Exception:
            logger.debug("No se pudieron listar los equipos del espacio", exc_info=True)
            ids = set()
    if team is not None and getattr(team, "id", None):
        ids.add(int(team.id))
    return ids


def carpetas_del_club(workspace, team, repository):
    """Las carpetas de biblioteca que ve este club, sea cual sea la categoría activa."""
    from .models import SessionTaskCollection

    qs = SessionTaskCollection.objects.filter(repository=repository)
    ids = equipos_del_espacio(workspace, team)
    if ids:
        return qs.filter(team_id__in=ids)
    # Sin espacio no se puede saber de quién es: se cae al equipo de referencia antes que
    # enseñar las carpetas de otro club.
    return qs.filter(team=team) if team is not None else qs.none()


def tarea_archivada_en_el_club(task, workspace):
    """¿Está esta tarea metida en una carpeta de biblioteca de este club?"""
    from .models import SessionTaskCollectionItem

    if not task or not getattr(task, "id", None):
        return False
    ids = equipos_del_espacio(workspace)
    if not ids:
        return False
    try:
        return SessionTaskCollectionItem.objects.filter(
            task_id=int(task.id), collection__team_id__in=ids
        ).exists()
    except Exception:
        logger.debug("No se pudo comprobar la carpeta de la tarea %s", getattr(task, "id", None), exc_info=True)
        return False
