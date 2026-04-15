from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone


TIME_LOSS_MINIMAL_MAX = 3
TIME_LOSS_MILD_MAX = 7
TIME_LOSS_MODERATE_MAX = 28


def categorize_time_loss(days: int) -> str:
    """
    Clasificación estándar de severidad por días de baja (time-loss).

    - 0-3: mínima
    - 4-7: leve
    - 8-28: moderada
    - 29+: grave
    """
    value = int(days or 0)
    if value <= TIME_LOSS_MINIMAL_MAX:
        return 'minima'
    if value <= TIME_LOSS_MILD_MAX:
        return 'leve'
    if value <= TIME_LOSS_MODERATE_MAX:
        return 'moderada'
    return 'grave'


def time_loss_days(injury_date: date | None, return_date: date | None, today: date | None = None) -> int:
    if not injury_date:
        return 0
    reference_day = today or timezone.localdate()
    end = return_date or reference_day
    if end < injury_date:
        return 0
    return int((end - injury_date).days) + 1


def estimate_return_date(
    injury_date: date | None,
    typical_min_days: int | None,
    typical_max_days: int | None,
    severity_grade: int | None = None,
) -> date | None:
    """
    Estima la fecha de alta en base a un rango de días.

    Si hay severidad:
    - grado 1: mínimo
    - grado 2: media
    - grado 3: máximo
    """
    if not injury_date:
        return None
    min_days = int(typical_min_days or 0)
    max_days = int(typical_max_days or 0)
    if max_days and min_days and max_days < min_days:
        min_days, max_days = max_days, min_days
    if not min_days and not max_days:
        return None
    if not max_days:
        max_days = min_days
    if not min_days:
        min_days = max_days

    grade = int(severity_grade or 0)
    if grade <= 1:
        chosen_days = min_days
    elif grade == 2:
        chosen_days = round((min_days + max_days) / 2)
    else:
        chosen_days = max_days
    return injury_date + timedelta(days=int(chosen_days))


@dataclass(frozen=True)
class InjuryMetrics:
    total_records: int = 0
    active_records: int = 0
    total_days_lost: int = 0
    active_days_lost: int = 0

