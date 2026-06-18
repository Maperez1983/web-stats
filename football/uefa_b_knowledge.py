from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


KNOWLEDGE_PATH = Path(settings.BASE_DIR) / "data" / "input" / "uefa_b_task_methodology.json"


@lru_cache(maxsize=1)
def load_uefa_b_knowledge() -> dict:
    try:
        data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def uefa_b_context_for_prompt() -> dict:
    data = load_uefa_b_knowledge()
    return {
        "title": str(data.get("title") or "")[:180],
        "session_design_checklist": data.get("session_design_checklist") if isinstance(data.get("session_design_checklist"), list) else [],
        "task_quality_rules": data.get("task_quality_rules") if isinstance(data.get("task_quality_rules"), list) else [],
        "didactic_formats": data.get("didactic_formats") if isinstance(data.get("didactic_formats"), list) else [],
        "age_and_level_guidance": data.get("age_and_level_guidance") if isinstance(data.get("age_and_level_guidance"), list) else [],
        "learning_climate": data.get("learning_climate") if isinstance(data.get("learning_climate"), list) else [],
        "match_connection": data.get("match_connection") if isinstance(data.get("match_connection"), list) else [],
    }
