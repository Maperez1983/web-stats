"""Helpers para gestionar equipos por categoría (ej. Cadete A/B)"""

from django.db.models import Q


def get_players_for_category(category_ref, include_related_divisions=False):
    """
    Obtiene jugadores de una categoría.

    Args:
        category_ref: ClubCategory instance
        include_related_divisions: Si True, incluye jugadores de todos los equipos
                                   de la categoría (A, B, C). Si False, solo el
                                   equipo actual.

    Returns:
        QuerySet de Player
    """
    from football.models import Player, Team

    if not category_ref:
        return Player.objects.none()

    # Equipos de la categoría
    teams_in_category = Team.objects.filter(category_ref=category_ref)

    if not include_related_divisions:
        # Solo jugadores del equipo principal (si hay uno seleccionado)
        return Player.objects.filter(team__category_ref=category_ref).select_related('team')
    else:
        # Todos los jugadores de todos los equipos de la categoría
        return Player.objects.filter(
            team__in=teams_in_category
        ).select_related('team').distinct()


def get_teams_in_same_category(team):
    """
    Obtiene otros equipos de la misma categoría.

    Args:
        team: Team instance

    Returns:
        QuerySet de otros Team en la misma categoría
    """
    from football.models import Team

    if not team or not team.category_ref:
        return Team.objects.none()

    return Team.objects.filter(
        category_ref=team.category_ref
    ).exclude(id=team.id)


def get_players_for_session(team):
    """
    Obtiene jugadores disponibles para sesiones/entrenamientos.

    Para sesiones (entrenamientos de categoría), siempre incluye
    todos los equipos de la categoría (A, B, C, etc.)

    Args:
        team: Team instance (equipo actual)

    Returns:
        QuerySet de Player
    """
    if not team or not team.category_ref:
        # Fallback: solo jugadores del equipo
        return team.player_set.filter(is_active=True) if team else None

    # Sesiones incluyen todos los equipos de la categoría
    return get_players_for_category(team.category_ref, include_related_divisions=True)
