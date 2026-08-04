"""A quién ve cada equipo en Dirección deportiva.

El objetivo de ojeo colgaba SOLO del club, así que el cadete y el senior veían exactamente la
misma dirección: no faltaba un filtro, faltaba el dato. Con `ScoutingTarget.team` cada categoría
tiene la suya.

Regla: se ve lo de tu equipo MÁS lo que no tiene equipo asignado. Lo segundo no es un descuido:
un ojeado del club todavía sin categoría decidida tiene que verse desde algún sitio, y ocultarlo
en todas las pantallas sería peor que enseñarlo de más.
"""

from django.db.models import Q


def objetivos_del_equipo(qs, team):
    """Filtra objetivos de ojeo por el equipo activo. Sin equipo, devuelve el queryset intacto.

    Antes se filtraba por `player__team`, el equipo del jugador LOCAL vinculado. Pero un ojeado
    es casi siempre alguien de fuera y no tiene ficha local, así que caía en la rama "sin
    jugador" y se veía desde todas las categorías: de ahí que el cadete viera la dirección del
    senior. Ahora manda el equipo del propio objetivo, y `player__team` sólo decide cuando el
    objetivo no lo tiene asignado.
    """
    if team is None:
        return qs
    team_id = getattr(team, 'id', team)
    if not team_id:
        return qs
    sin_equipo_propio = Q(team__isnull=True) & (Q(player__team_id=team_id) | Q(player__isnull=True))
    return qs.filter(Q(team_id=team_id) | sin_equipo_propio)


def equipo_para_nuevo_objetivo(team):
    """El equipo que se le pone a un objetivo nuevo: el activo, para que nazca en su categoría
    en vez de caer en el saco común del club."""
    return team if getattr(team, 'id', None) else None
