from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


KNOWLEDGE_PATH = Path(settings.BASE_DIR) / "data" / "input" / "fifa11_injury_prevention_methodology.json"


@lru_cache(maxsize=1)
def load_fifa11_injury_knowledge() -> dict:
    try:
        data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def fifa11_injury_context_for_prompt() -> dict:
    data = load_fifa11_injury_knowledge()
    return {
        "title": str(data.get("title") or "")[:180],
        "medical_safety": data.get("medical_safety") if isinstance(data.get("medical_safety"), dict) else {},
        "fifa11plus_structure": data.get("fifa11plus_structure") if isinstance(data.get("fifa11plus_structure"), list) else [],
        "implementation_rules": data.get("implementation_rules") if isinstance(data.get("implementation_rules"), list) else [],
        "age_adaptations": data.get("age_adaptations") if isinstance(data.get("age_adaptations"), list) else [],
        "injury_risk_focus": data.get("injury_risk_focus") if isinstance(data.get("injury_risk_focus"), list) else [],
        "return_to_training_framework": data.get("return_to_training_framework") if isinstance(data.get("return_to_training_framework"), list) else [],
        "weekly_integration": data.get("weekly_integration") if isinstance(data.get("weekly_integration"), list) else [],
        "ollama_usage_rules": data.get("ollama_usage_rules") if isinstance(data.get("ollama_usage_rules"), list) else [],
    }
