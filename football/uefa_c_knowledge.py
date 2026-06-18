from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


KNOWLEDGE_PATH = Path(settings.BASE_DIR) / "data" / "input" / "uefa_c_task_methodology.json"


@lru_cache(maxsize=1)
def load_uefa_c_knowledge() -> dict:
    try:
        data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def uefa_c_context_for_prompt() -> dict:
    data = load_uefa_c_knowledge()
    return {
        "title": str(data.get("title") or "")[:180],
        "course_areas": data.get("course_areas") if isinstance(data.get("course_areas"), list) else [],
        "formative_task_principles": data.get("formative_task_principles") if isinstance(data.get("formative_task_principles"), list) else [],
        "session_structure": data.get("session_structure") if isinstance(data.get("session_structure"), list) else [],
        "task_design_controls": data.get("task_design_controls") if isinstance(data.get("task_design_controls"), list) else [],
        "task_scales": data.get("task_scales") if isinstance(data.get("task_scales"), list) else [],
        "individual_capabilities": data.get("individual_capabilities") if isinstance(data.get("individual_capabilities"), dict) else {},
        "learning_climate": data.get("learning_climate") if isinstance(data.get("learning_climate"), list) else [],
        "ollama_usage_rules": data.get("ollama_usage_rules") if isinstance(data.get("ollama_usage_rules"), list) else [],
    }
