"""
La valoración de un jugador es la MEDIA del cuerpo técnico, no la de uno.

Antes cada `PlayerEvaluation` era una isla: la "media" que se enseñaba era la de las cinco
áreas dentro de UNA valoración, así que lo que veías dependía de quién la hubiera escrito y
de cuál fuera la última. Aquí se consolida:

- Cada miembro del cuerpo técnico mete la suya. **Un miembro, un voto**: si alguien valora
  tres veces en la temporada, cuenta su última, no las tres. Si no, quien más escribe manda.
- El jugador puede autovalorarse, y su percepción **no entra en la media**. Se devuelve
  aparte, porque la distancia entre lo que él cree y lo que ve el cuerpo técnico es de los
  datos más útiles que da una evaluación — pero es otra cosa, no un voto más.
- Sólo cuentan las CERRADAS. Un borrador es trabajo a medias de una persona, no una opinión
  emitida.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

# Las cinco áreas que se promedian, más el global.
AREA_FIELDS = (
    ("technical_rating", "Técnica"),
    ("tactical_rating", "Táctica"),
    ("physical_rating", "Física"),
    ("mental_rating", "Mental"),
    ("social_rating", "Social"),
)


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _latest_per_author(evaluations):
    """
    Un miembro, un voto: se queda con la última valoración de cada autor.

    Las que no tienen autor (importadas o antiguas) se tratan como votos independientes: no
    se pueden agrupar, y descartarlas seria perder informacion real.
    """
    latest = {}
    loose = []
    for evaluation in evaluations:
        author_id = getattr(evaluation, "created_by_id", None)
        if not author_id:
            loose.append(evaluation)
            continue
        current = latest.get(author_id)
        if current is None or _sort_key(evaluation) > _sort_key(current):
            latest[author_id] = evaluation
    return list(latest.values()) + loose


def _sort_key(evaluation):
    from datetime import date

    return (getattr(evaluation, "evaluated_on", None) or date.min, int(getattr(evaluation, "id", 0) or 0))


def staff_consensus(player, *, club_season=None, evaluations=None):
    """
    Devuelve la foto consolidada de un jugador.

    {
      'overall': 6.4,                  # media del cuerpo técnico (None si nadie ha valorado)
      'areas': [{'key','label','value'}...],
      'voters': 3,                     # cuántos miembros la sostienen
      'contributions': [PlayerEvaluation...],   # la última de cada miembro
      'self_assessment': PlayerEvaluation|None, # la del jugador, APARTE
      'gap': -0.8,                     # autopercepción menos media del staff
    }
    """
    empty = {
        "overall": None,
        "areas": [{"key": key, "label": label, "value": None} for key, label in AREA_FIELDS],
        "voters": 0,
        "contributions": [],
        "self_assessment": None,
        "gap": None,
    }
    # Se admite pasar la lista ya cargada sin jugador: así quien necesita la media de media
    # plantilla (la pizarra) hace UNA consulta y no una por jugador.
    if player is None and evaluations is None:
        return empty

    try:
        from .models import PlayerEvaluation

        if evaluations is None:
            qs = PlayerEvaluation.objects.filter(
                player=player, status=PlayerEvaluation.STATUS_CLOSED
            ).select_related("created_by")
            if club_season is not None:
                qs = qs.filter(club_season=club_season)
            evaluations = list(qs)

        staff = [e for e in evaluations if getattr(e, "author_kind", PlayerEvaluation.AUTHOR_STAFF) != PlayerEvaluation.AUTHOR_SELF]
        selves = [e for e in evaluations if getattr(e, "author_kind", "") == PlayerEvaluation.AUTHOR_SELF]

        contributions = sorted(_latest_per_author(staff), key=_sort_key, reverse=True)
        self_assessment = max(selves, key=_sort_key) if selves else None

        areas = []
        for key, label in AREA_FIELDS:
            areas.append({
                "key": key,
                "label": label,
                "value": _mean([_num(getattr(e, key, None)) for e in contributions]),
            })

        # El global es la media de las medias de cada miembro (no la media de las áreas):
        # respeta el juicio de cada uno aunque uno puntúe sólo algunas áreas.
        overall = _mean([_num(e.average_rating) for e in contributions])

        gap = None
        if self_assessment is not None and overall is not None:
            own = _num(self_assessment.average_rating)
            if own is not None:
                gap = round(own - overall, 1)

        return {
            "overall": overall,
            "areas": areas,
            "voters": len(contributions),
            "contributions": contributions,
            "self_assessment": self_assessment,
            "gap": gap,
        }
    except Exception:
        logger.exception("No se pudo calcular el consenso de valoración del jugador %s",
                         getattr(player, "id", None))
        return empty
