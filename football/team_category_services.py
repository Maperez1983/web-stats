"""
Categoría de un equipo, deducida de su competición.

La regla del club: un CLUB por un lado y sus EQUIPOS por categoría (`Team.category`) por
otro — la categoría es el sub-identificador dentro del club. Los equipos importados de las
ligas entraban con el nombre del club como nombre de equipo y SIN categoría: 52 de 77 en
producción. Así no se distingue el cadete del Alhaurín de su senior.

La categoría no se inventa: sale del nombre del grupo o de la competición, que es donde la
federación la escribe ("3ª División Andaluza Cadete Grupo 1", "División de Honor Andaluza").
"""

from __future__ import annotations

import logging
import re
import unicodedata


logger = logging.getLogger(__name__)


# De más específica a menos: "prebenjamín" contiene "benjamín", así que el orden importa.
CATEGORIAS = (
    ("Prebenjamín", ("prebenjamin", "pre benjamin", "pre-benjamin")),
    ("Benjamín", ("benjamin",)),
    ("Alevín", ("alevin",)),
    ("Infantil", ("infantil",)),
    ("Cadete", ("cadete",)),
    ("Juvenil", ("juvenil",)),
    ("Bebé", ("bebe", "chupetin", "querubin")),
    ("Femenino", ("femenino", "femenina")),
    ("Veterano", ("veterano", "veteranos")),
    # Senior va al final: sus nombres ("división de honor", "primera andaluza") no llevan la
    # palabra categoría, así que sólo se aplica cuando NINGUNA de las anteriores encaja.
    ("Senior", ("division de honor", "primera andaluza", "segunda andaluza", "tercera andaluza",
                "1a andaluza", "2a andaluza", "3a andaluza", "senior", "aficionado", "regional")),
)


def _plano(texto):
    crudo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", crudo.lower()).strip()


def deducir_categoria(*textos):
    """Primera categoría reconocida en los textos dados (nombre de grupo, competición…)."""
    plano = " ".join(_plano(t) for t in textos if t)
    if not plano:
        return ""
    for etiqueta, claves in CATEGORIAS:
        for clave in claves:
            if clave in plano:
                return etiqueta
    return ""


def categoria_para_equipo(team):
    """
    Categoría del equipo a partir de su grupo y su competición.

    OJO con el orden: el grupo es más específico que la competición ("Grupo 1 (Málaga)" no
    dice nada, pero "3ª División Andaluza Cadete" sí), así que se miran los dos juntos.
    """
    grupo = getattr(team, "group", None)
    season = getattr(grupo, "season", None) if grupo else None
    competicion = getattr(season, "competition", None) if season else None
    return deducir_categoria(
        getattr(grupo, "name", ""),
        getattr(competicion, "name", ""),
        getattr(season, "name", ""),
    )


def rellenar_categorias(teams, *, sobrescribir=False):
    """
    Pone la categoría a los equipos que no la tengan. Devuelve un resumen legible.

    Con `sobrescribir=False` NO toca lo que ya esté escrito a mano: el club puede haber
    puesto "Cadete A" y eso es más preciso que lo que diga la competición.
    """
    resumen = {"actualizados": [], "sin_pistas": [], "ya_tenian": []}
    for team in teams:
        actual = str(getattr(team, "category", "") or "").strip()
        if actual and not sobrescribir:
            resumen["ya_tenian"].append(team.name)
            continue
        categoria = categoria_para_equipo(team)
        if not categoria:
            resumen["sin_pistas"].append(team.name)
            continue
        if categoria == actual:
            resumen["ya_tenian"].append(team.name)
            continue
        team.category = categoria
        team.save(update_fields=["category"])
        resumen["actualizados"].append(f"{team.name} → {categoria}")
    return resumen
