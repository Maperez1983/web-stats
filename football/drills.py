from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Drill:
    id: str
    label: str
    category: str
    icon_static_path: str
    description: str = ""
    tags: Tuple[str, ...] = ()


DRILL_CATALOG: List[Drill] = [
    Drill(
        id="run_easy",
        label="Carrera suave",
        category="running",
        icon_static_path="football/images/drills/running/run_easy.svg",
        tags=("warmup", "running"),
    ),
    Drill(
        id="a_skip",
        label="Skipping (rodillas arriba)",
        category="running_technique",
        icon_static_path="football/images/drills/running/a_skip.svg",
        tags=("warmup", "running", "technique"),
    ),
    Drill(
        id="butt_kicks",
        label="Talones al glúteo",
        category="running_technique",
        icon_static_path="football/images/drills/running/butt_kicks.svg",
        tags=("warmup", "running", "technique"),
    ),
    Drill(
        id="side_shuffle",
        label="Desplazamiento lateral",
        category="running_technique",
        icon_static_path="football/images/drills/running/side_shuffle.svg",
        tags=("warmup", "agility"),
    ),
    Drill(
        id="carioca",
        label="Carioca (cruce lateral)",
        category="running_technique",
        icon_static_path="football/images/drills/running/carioca.svg",
        tags=("warmup", "agility"),
    ),
    Drill(
        id="ankling",
        label="Pies rápidos (ankling)",
        category="running_technique",
        icon_static_path="football/images/drills/running/ankling.svg",
        tags=("warmup", "running", "technique"),
    ),
    Drill(
        id="bounding",
        label="Zancadas amplias (bounding)",
        category="running_technique",
        icon_static_path="football/images/drills/running/bounding.svg",
        tags=("warmup", "running", "power"),
    ),
    Drill(
        id="lunge_walk",
        label="Zancadas caminando",
        category="mobility",
        icon_static_path="football/images/drills/running/lunge_walk.svg",
        tags=("warmup", "mobility"),
    ),
    Drill(
        id="hip_open_close",
        label="Movilidad cadera (abre/cierra)",
        category="mobility",
        icon_static_path="football/images/drills/running/hip_open_close.svg",
        tags=("warmup", "mobility"),
    ),
    Drill(
        id="hamstring_sweep",
        label="Isquios (barrido)",
        category="mobility",
        icon_static_path="football/images/drills/running/hamstring_sweep.svg",
        tags=("warmup", "mobility"),
    ),
    # Carga física (campo)
    Drill(
        id="acceleration",
        label="Aceleraciones",
        category="physical_field",
        icon_static_path="football/images/drills/physical/acceleration.svg",
        tags=("physical", "field", "speed"),
    ),
    Drill(
        id="max_sprint",
        label="Sprint máximo",
        category="physical_field",
        icon_static_path="football/images/drills/physical/max_sprint.svg",
        tags=("physical", "field", "speed"),
    ),
    Drill(
        id="deceleration",
        label="Frenadas (deceleración)",
        category="physical_field",
        icon_static_path="football/images/drills/physical/deceleration.svg",
        tags=("physical", "field", "cod"),
    ),
    Drill(
        id="change_direction",
        label="Cambios de dirección (COD)",
        category="physical_field",
        icon_static_path="football/images/drills/physical/change_direction.svg",
        tags=("physical", "field", "cod"),
    ),
    Drill(
        id="shuttle_run",
        label="Ida y vuelta (shuttle)",
        category="physical_field",
        icon_static_path="football/images/drills/physical/shuttle_run.svg",
        tags=("physical", "field", "hiit"),
    ),
    Drill(
        id="jump_land",
        label="Saltos + aterrizaje",
        category="plyo",
        icon_static_path="football/images/drills/physical/jump_land.svg",
        tags=("physical", "field", "plyo"),
    ),
    Drill(
        id="pogo_hops",
        label="Saltitos (pogo hops)",
        category="plyo",
        icon_static_path="football/images/drills/physical/pogo_hops.svg",
        tags=("physical", "field", "plyo"),
    ),
    # Carga física (gimnasio / fuerza)
    Drill(
        id="squat",
        label="Sentadilla",
        category="strength",
        icon_static_path="football/images/drills/physical/squat.svg",
        tags=("physical", "gym", "strength"),
    ),
    Drill(
        id="hinge",
        label="Bisagra cadera (hinge)",
        category="strength",
        icon_static_path="football/images/drills/physical/hinge.svg",
        tags=("physical", "gym", "strength"),
    ),
    Drill(
        id="split_squat",
        label="Zancada (split squat)",
        category="strength",
        icon_static_path="football/images/drills/physical/split_squat.svg",
        tags=("physical", "gym", "strength"),
    ),
    Drill(
        id="nordic",
        label="Nórdicos (isquios)",
        category="prehab",
        icon_static_path="football/images/drills/physical/nordic.svg",
        tags=("physical", "gym", "prehab", "hamstring"),
    ),
    Drill(
        id="calf_raise",
        label="Gemelo (elevación)",
        category="prehab",
        icon_static_path="football/images/drills/physical/calf_raise.svg",
        tags=("physical", "gym", "prehab"),
    ),
    Drill(
        id="plank",
        label="Plancha",
        category="core",
        icon_static_path="football/images/drills/physical/plank.svg",
        tags=("physical", "gym", "core"),
    ),
    Drill(
        id="side_plank",
        label="Plancha lateral",
        category="core",
        icon_static_path="football/images/drills/physical/side_plank.svg",
        tags=("physical", "gym", "core"),
    ),
    Drill(
        id="push_up",
        label="Flexiones",
        category="strength",
        icon_static_path="football/images/drills/physical/push_up.svg",
        tags=("physical", "gym", "strength"),
    ),
    Drill(
        id="band_row",
        label="Remo con goma",
        category="strength",
        icon_static_path="football/images/drills/physical/band_row.svg",
        tags=("physical", "gym", "strength"),
    ),
]


DRILL_LIBRARY: Dict[str, Drill] = {item.id: item for item in DRILL_CATALOG}


def normalize_drill_ids(raw: object, *, max_items: int = 24) -> List[str]:
    """
    Accepts:
    - JSON list of strings: ["a_skip", "butt_kicks"]
    - JSON list of dicts: [{"id":"a_skip"}, {"id":"butt_kicks"}]
    - comma-separated string: "a_skip, butt_kicks"
    Returns a de-duplicated ordered list of ids (keeps first occurrence).
    """
    items: List[str] = []

    def push(value: object) -> None:
        if len(items) >= int(max_items):
            return
        text = str(value or "").strip()
        if not text:
            return
        items.append(text)

    if raw is None:
        return []

    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        # JSON?
        if s.startswith("[") and s.endswith("]"):
            try:
                import json

                parsed = json.loads(s)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, str):
                        push(entry)
                    elif isinstance(entry, dict):
                        push(entry.get("id") or entry.get("key") or entry.get("name") or "")
                return _dedupe_keep_order(items)
        # CSV fallback
        for part in s.split(","):
            push(part)
        return _dedupe_keep_order(items)

    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                push(entry)
            elif isinstance(entry, dict):
                push(entry.get("id") or entry.get("key") or entry.get("name") or "")
        return _dedupe_keep_order(items)

    if isinstance(raw, dict):
        # Sometimes stored as {"items":[...]}
        maybe = raw.get("items") if isinstance(raw.get("items"), list) else []
        for entry in maybe:
            if isinstance(entry, str):
                push(entry)
            elif isinstance(entry, dict):
                push(entry.get("id") or entry.get("key") or entry.get("name") or "")
        return _dedupe_keep_order(items)

    push(raw)
    return _dedupe_keep_order(items)


def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        v = str(value or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def drill_cards(ids: Iterable[str]) -> List[dict]:
    cards: List[dict] = []
    for drill_id in ids:
        item = DRILL_LIBRARY.get(str(drill_id or "").strip())
        if not item:
            continue
        cards.append(
            {
                "id": item.id,
                "label": item.label,
                "category": item.category,
                "icon_static_path": item.icon_static_path,
                "description": item.description,
            }
        )
    return cards
