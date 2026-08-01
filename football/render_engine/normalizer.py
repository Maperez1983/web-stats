from __future__ import annotations

from typing import Any, Dict, List, Tuple


def parse_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def normalize_animation_timeline(raw_timeline: Any) -> List[Dict[str, Any]]:
    from .. import views

    return views._normalize_animation_timeline(raw_timeline)


def extract_task_canvas_state(task: Any) -> Tuple[Dict[str, Any], int, int]:
    from .. import views

    return views._extract_canvas_state_for_preview(task)


def resolve_task_team(task: Any) -> Any:
    try:
        return task.session.microcycle.team
    except Exception:
        return None


def resolve_task_tactical_layout(task: Any) -> Dict[str, Any]:
    tactical_layout = getattr(task, 'tactical_layout', None)
    return tactical_layout if isinstance(tactical_layout, dict) else {}


def resolve_task_meta(task: Any) -> Dict[str, Any]:
    tactical_layout = resolve_task_tactical_layout(task)
    meta = tactical_layout.get('meta')
    return meta if isinstance(meta, dict) else {}
