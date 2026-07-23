"""
Temporada de competición vigente (federación), derivada del calendario.

Distinta de la temporada interna de club (`WorkspaceSeason`, ver `season_history_services`):
aquí hablamos de la temporada de la federación (`Season`, colgando de `Competition`), que es la
que gobierna `Team.group` -> `Group.season` y, por tanto, clasificación y próximo rival.

Motivación: hasta ahora la temporada estaba escrita a mano ('2025/2026') en varios puntos del
código, así que cada 1 de julio la portada del entrenador se quedaba anclada a la temporada
anterior. Aquí la derivamos de la fecha, con corte configurable y override explícito por entorno.
"""

from __future__ import annotations

import os
import re

from django.utils import timezone

# Mes en el que arranca la temporada (1-12). Julio por defecto: en julio ya se compite/inscribe
# para la campaña que empieza en agosto/septiembre.
SEASON_START_MONTH_ENV = 'COMPETITION_SEASON_START_MONTH'
DEFAULT_SEASON_START_MONTH = 7

# Override duro, por si la federación nombra la temporada de forma no derivable (ej. '2026').
SEASON_NAME_ENV = 'COMPETITION_SEASON_NAME'

_SEASON_NAME_RE = re.compile(r'(\d{4})\s*[/\-–]\s*(\d{2,4})')


def _season_start_month():
    raw = str(os.getenv(SEASON_START_MONTH_ENV, '') or '').strip()
    try:
        month = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SEASON_START_MONTH
    return month if 1 <= month <= 12 else DEFAULT_SEASON_START_MONTH


def current_season_start_year(today=None):
    """Año en el que arranca la temporada vigente. 2026-07-23 -> 2026; 2026-03-01 -> 2025."""
    today = today or timezone.localdate()
    return int(today.year) if int(today.month) >= _season_start_month() else int(today.year) - 1


def current_season_name(separator='/', today=None):
    """Nombre de la temporada vigente. Formato `Season.name`: '2026/2027'."""
    override = str(os.getenv(SEASON_NAME_ENV, '') or '').strip()
    if override:
        return normalize_season_name(override, separator=separator) or override
    start_year = current_season_start_year(today)
    return f'{start_year}{separator}{start_year + 1}'


def current_universo_season_name(today=None):
    """Nombre de la temporada vigente tal y como la publica Universo RFAF: '2026-2027'."""
    return current_season_name(separator='-', today=today)


def normalize_season_name(value, separator='/'):
    """Normaliza '2026-27', '2026/2027', '2026 - 2027' a un formato canónico ('2026/2027')."""
    match = _SEASON_NAME_RE.search(str(value or ''))
    if not match:
        return ''
    start_year = int(match.group(1))
    end_raw = match.group(2)
    end_year = int(end_raw) if len(end_raw) == 4 else (start_year // 100) * 100 + int(end_raw)
    return f'{start_year}{separator}{end_year}'


def season_names_match(left, right):
    """Compara dos nombres de temporada ignorando el separador ('2026-2027' == '2026/2027')."""
    left_normalized = normalize_season_name(left)
    right_normalized = normalize_season_name(right)
    if left_normalized and right_normalized:
        return left_normalized == right_normalized
    return str(left or '').strip().casefold() == str(right or '').strip().casefold()


def pick_current_season_row(rows, name_key='nombre', today=None):
    """
    Elige la fila de temporada vigente en un listado del proveedor.

    Antes se buscaba la cadena literal '2025-2026' y, si no aparecía, se cogía `rows[0]` —
    es decir, lo que el proveedor devolviera primero. Ahora se busca la temporada derivada del
    calendario y sólo se cae a la primera fila como último recurso.
    """
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    if not rows:
        return None
    wanted = current_universo_season_name(today)
    for row in rows:
        if season_names_match(row.get(name_key), wanted):
            return row
    return rows[0]
