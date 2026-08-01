from __future__ import annotations

from typing import Any, Dict

from ..premium_surface_preview import render_stadium_native_preview_data_url


def render_task_preview_2d(
    canvas_state: Dict[str, Any],
    *,
    canvas_width: int,
    canvas_height: int,
    pitch_orientation: str,
    grass_style: str,
) -> str:
    safe_state = canvas_state if isinstance(canvas_state, dict) else {'objects': []}
    return render_stadium_native_preview_data_url(
        safe_state,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pitch_orientation=pitch_orientation,
    )
