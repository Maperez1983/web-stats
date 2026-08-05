"""Una carpeta de la biblioteca es material del club, no de una categoría.

Las tareas importadas de un libro se guardan colgando del equipo principal (el senior), que es
quien tiene la biblioteca. Pero no son del senior: son del club. Desde que las listas filtran
por categoría, al cadete le desaparecían — y abrir una por su id daba "no encontrada".

La regla NO es "toda carpeta se comparte": la biblioteca de Aitor es del senior y ahí se
queda. Se comparten las carpetas de material que entra de fuera (un libro, un PPT), que no
son de nadie en concreto. Fuera del espacio de trabajo no se ve ninguna.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Carpetas que son del club entero y no de la categoría que las guarda. Lo importado de un
# libro o de un PPT no pertenece al senior por haber caído en su biblioteca.
CARPETAS_DEL_CLUB = {'tareas importadas'}


def es_carpeta_compartida(nombre):
    return str(nombre or '').strip().lower() in CARPETAS_DEL_CLUB


def _filtro_de_nombres_compartidos(prefijo=''):
    """Q que casa con los nombres compartidos sin distinguir mayúsculas ni acentos raros."""
    from django.db.models import Q

    campo = f'{prefijo}name__iexact'
    filtro = Q(pk__in=[])
    for nombre in CARPETAS_DEL_CLUB:
        filtro |= Q(**{campo: nombre})
    return filtro


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


def carpetas_visibles(workspace, team, repository=None):
    """Las carpetas propias de la categoría, más las compartidas del resto del club.

    `repository=None` las trae todas: tradicional o interactiva es de dónde entró el material,
    no una biblioteca aparte.
    """
    from django.db.models import Q

    from .models import SessionTaskCollection

    qs = SessionTaskCollection.objects.all() if repository is None else SessionTaskCollection.objects.filter(repository=repository)
    if team is None or not getattr(team, 'id', None):
        return qs.none()
    propias = Q(team_id=int(team.id))
    ids = equipos_del_espacio(workspace, team)
    if not ids:
        # Sin espacio no se puede saber de quién es: sólo las propias, antes que enseñar
        # las carpetas de otro club.
        return qs.filter(propias)
    compartidas = Q(team_id__in=ids) & _filtro_de_nombres_compartidos()
    return qs.filter(propias | compartidas)


def tarea_archivada_en_el_club(task, workspace):
    """¿Está esta tarea metida en una carpeta de biblioteca de este club?"""
    from .models import SessionTaskCollectionItem

    if not task or not getattr(task, "id", None):
        return False
    ids = equipos_del_espacio(workspace)
    if not ids:
        return False
    try:
        return (
            SessionTaskCollectionItem.objects.filter(task_id=int(task.id), collection__team_id__in=ids)
            .filter(_filtro_de_nombres_compartidos('collection__'))
            .exists()
        )
    except Exception:
        logger.debug("No se pudo comprobar la carpeta de la tarea %s", getattr(task, "id", None), exc_info=True)
        return False


def ids_de_tareas_compartidas(workspace):
    """Ids de las tareas archivadas en las carpetas que el club comparte entre categorías."""
    from .models import SessionTaskCollectionItem

    ids = equipos_del_espacio(workspace)
    if not ids:
        return set()
    try:
        return {
            int(tid)
            for tid in SessionTaskCollectionItem.objects.filter(collection__team_id__in=ids)
            .filter(_filtro_de_nombres_compartidos('collection__'))
            .values_list('task_id', flat=True)
            if tid
        }
    except Exception:
        logger.debug('No se pudieron listar las tareas compartidas del club', exc_info=True)
        return set()


def ids_de_tareas_compartidas_de_un_equipo(team):
    """Igual que `ids_de_tareas_compartidas`, pero partiendo de un EQUIPO.

    El recomendador se ejecuta desde una sesión y no tiene el espacio de trabajo a mano, así
    que se resuelve por el club del equipo. Si el equipo no tiene club, se mira sólo el suyo:
    peor ver de menos que colar material de otro club.
    """
    from .models import SessionTaskCollectionItem, Team

    if team is None or not getattr(team, 'id', None):
        return set()
    ids_equipos = {int(team.id)}
    club_id = getattr(team, 'club_id', None)
    if club_id:
        try:
            ids_equipos |= {
                int(tid) for tid in Team.objects.filter(club_id=club_id).values_list('id', flat=True) if tid
            }
        except Exception:
            logger.debug('No se pudieron listar los equipos del club', exc_info=True)
    try:
        return {
            int(tid)
            for tid in SessionTaskCollectionItem.objects.filter(collection__team_id__in=ids_equipos)
            .filter(_filtro_de_nombres_compartidos('collection__'))
            .values_list('task_id', flat=True)
            if tid
        }
    except Exception:
        logger.debug('No se pudieron listar las tareas compartidas del equipo', exc_info=True)
        return set()


def equipos_de_la_categoria(workspace, team):
    """
    Ids de los equipos del club que comparten categoría con el de referencia.

    Un club puede tener dos equipos de la misma categoría (Cadete A y Cadete B). El material
    de trabajo es el mismo: lo que prepara el A le sirve al B. Filtrar por equipo exacto dejaba
    al staff del B con la biblioteca vacía.

    Si el equipo no tiene categoría puesta no se agrupa con nadie: mejor ver de menos que
    mezclar el material del alevín con el del senior.
    """
    from .models import Team

    ids = {int(team.id)} if team is not None and getattr(team, 'id', None) else set()
    categoria = str(getattr(team, 'category', '') or '').strip()
    if not categoria:
        return ids
    del_club = equipos_del_espacio(workspace, team)
    if not del_club:
        return ids
    try:
        ids |= {
            int(tid)
            for tid in Team.objects.filter(id__in=del_club, category__iexact=categoria).values_list('id', flat=True)
            if tid
        }
    except Exception:
        logger.debug('No se pudieron listar los equipos de la categoría', exc_info=True)
    return ids
