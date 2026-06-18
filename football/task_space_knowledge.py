from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings


KNOWLEDGE_PATH = Path(settings.BASE_DIR) / "data" / "input" / "task_space_methodology.json"


@lru_cache(maxsize=1)
def load_task_space_knowledge() -> dict:
    try:
        data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _to_float(value):
    try:
        if value is None:
            return None
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        parsed = float(text)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def parse_dimensions(value):
    raw = str(value or "").strip().lower().replace("×", "x")
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*x\s*(\d+(?:[,.]\d+)?)", raw)
    if not match:
        return None, None
    return _to_float(match.group(1)), _to_float(match.group(2))


def classify_space_band(m2_per_player, knowledge=None):
    data = knowledge if isinstance(knowledge, dict) else load_task_space_knowledge()
    value = _to_float(m2_per_player)
    if value is None:
        return None
    bands = data.get("space_bands") if isinstance(data.get("space_bands"), list) else []
    for band in bands:
        if not isinstance(band, dict):
            continue
        min_v = _to_float(band.get("min"))
        max_v = _to_float(band.get("max"))
        min_ok = min_v is None or value >= min_v
        max_ok = max_v is None or value < max_v
        if min_ok and max_ok:
            return band
    return None


def classify_player_band(players, knowledge=None):
    data = knowledge if isinstance(knowledge, dict) else load_task_space_knowledge()
    total = _to_float(players)
    if total is None:
        return None, False
    # La tabla metodologica trabaja por jugadores de campo por equipo. En el formulario
    # tenemos total de participantes, asi que aproximamos a mitad por equipo.
    per_team = max(1, int(round(total / 2)))
    bands = data.get("player_bands") if isinstance(data.get("player_bands"), list) else []
    fallback = None
    for band in bands:
        if not isinstance(band, dict):
            continue
        fallback = band
        min_v = int(band.get("min_per_team") or 0)
        max_v = int(band.get("max_per_team") or 0)
        if min_v <= per_team <= max_v:
            return band, False
    return fallback, True


def calculate_task_space_profile(*, width=None, length=None, players=None, dimensions=None, objective=""):
    data = load_task_space_knowledge()
    w = _to_float(width)
    l = _to_float(length)
    if (w is None or l is None) and dimensions:
        w, l = parse_dimensions(dimensions)
    p = _to_float(players)
    if w is None or l is None or p is None:
        return {"ok": False, "error": "missing_dimensions_or_players"}

    area = w * l
    m2_per_player = area / p if p else None
    space_band = classify_space_band(m2_per_player, data)
    player_band, player_fallback = classify_player_band(p, data)
    if not space_band or not player_band:
        return {"ok": False, "error": "unclassified", "area_m2": round(area, 1)}

    matrix = data.get("matrix") if isinstance(data.get("matrix"), list) else []
    row = next(
        (
            item
            for item in matrix
            if isinstance(item, dict)
            and item.get("space_band") == space_band.get("key")
            and item.get("player_band") == player_band.get("key")
        ),
        {},
    )
    focus_key = str(row.get("focus") or "").strip()
    definitions = data.get("focus_definitions") if isinstance(data.get("focus_definitions"), dict) else {}
    focus = definitions.get(focus_key) if isinstance(definitions.get(focus_key), dict) else {}
    align = data.get("objective_alignment") if isinstance(data.get("objective_alignment"), dict) else {}
    objective_key = str(objective or "").strip().lower()
    expected = align.get(objective_key) if isinstance(align.get(objective_key), list) else []
    is_aligned = not expected or focus_key in expected

    recommendation = (
        f"{round(m2_per_player, 1)} m2/j con {int(p)} participantes: orienta la tarea a "
        f"{focus.get('short_label') or focus.get('label') or focus_key}."
    )
    if not is_aligned:
        recommendation += " Si ese no era el objetivo, ajusta dimensiones, numero de jugadores o reglas."
    if player_fallback:
        recommendation += " La tabla original llega hasta 10 jugadores por equipo; se aplica el tramo mas cercano."

    return {
        "ok": True,
        "width_m": round(w, 1),
        "length_m": round(l, 1),
        "players": int(p),
        "area_m2": round(area, 1),
        "m2_per_player": round(m2_per_player, 1),
        "space_band": space_band,
        "player_band": player_band,
        "focus_key": focus_key,
        "focus": focus,
        "priority": int(row.get("priority") or 0),
        "aligned_with_objective": bool(is_aligned),
        "recommendation": recommendation,
    }


def task_space_context_for_prompt() -> dict:
    data = load_task_space_knowledge()
    return {
        "title": str(data.get("title") or "")[:180],
        "calculation": data.get("calculation") if isinstance(data.get("calculation"), dict) else {},
        "player_bands": data.get("player_bands") if isinstance(data.get("player_bands"), list) else [],
        "space_bands": data.get("space_bands") if isinstance(data.get("space_bands"), list) else [],
        "focus_definitions": data.get("focus_definitions") if isinstance(data.get("focus_definitions"), dict) else {},
        "matrix": data.get("matrix") if isinstance(data.get("matrix"), list) else [],
        "objective_alignment": data.get("objective_alignment") if isinstance(data.get("objective_alignment"), dict) else {},
        "microcycle_hints": data.get("microcycle_hints") if isinstance(data.get("microcycle_hints"), list) else [],
    }
