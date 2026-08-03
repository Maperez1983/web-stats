"""
Qué equipos puede ver un club.

`Team` es una tabla global: ahí conviven los equipos propios de cada club cliente y los
equipos ajenos que se importan de la federación para jugar contra ellos. Los selectores de
rival y de análisis listaban `Team.objects.all()`, así que a un club le aparecían como
posibles rivales las categorías internas de OTRO club cliente. Eso no es un rival: es la
plantilla de otra empresa que paga el mismo programa.

La regla: se ven los equipos SIN dueño (los federativos, que son de todos) y los del club
propio. Los que pertenecen al espacio de otro club, no.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def workspace_ids_de(team):
    """Espacios de trabajo a los que pertenece un equipo (normalmente uno, o ninguno)."""
    from .models import WorkspaceTeam

    if not team or not getattr(team, "id", None):
        return set()
    try:
        return {
            int(wid)
            for wid in WorkspaceTeam.objects.filter(team=team).values_list("workspace_id", flat=True)
            if wid
        }
    except Exception:
        logger.debug("No se pudieron leer los espacios del equipo %s", getattr(team, "id", None), exc_info=True)
        return set()


def ids_de_equipos_ajenos(team=None, *, workspace=None):
    """
    Ids de equipos que son de OTRO club cliente y por tanto no se enseñan.

    Se puede pasar el equipo de referencia o directamente el espacio de trabajo. Si no se
    puede determinar de quién es el que pregunta, no se oculta nada: mejor de más que
    romper una pantalla por una consulta que falle.
    """
    from .models import WorkspaceTeam

    propios = {int(getattr(workspace, "id", 0) or 0)} if workspace is not None else set()
    propios = {wid for wid in propios if wid} or workspace_ids_de(team)
    if not propios:
        return set()
    try:
        return {
            int(tid)
            for tid in WorkspaceTeam.objects.exclude(workspace_id__in=propios).values_list("team_id", flat=True)
            if tid
        }
    except Exception:
        logger.debug("No se pudieron listar los equipos de otros clubes", exc_info=True)
        return set()


def excluir_equipos_ajenos(queryset, team=None, *, workspace=None):
    """Quita del queryset los equipos que pertenecen a otro club cliente."""
    ajenos = ids_de_equipos_ajenos(team, workspace=workspace)
    return queryset.exclude(id__in=ajenos) if ajenos else queryset
