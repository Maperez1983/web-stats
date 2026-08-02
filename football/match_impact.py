MATCH_IMPACT_OPTIONS = {
    "chance_created": {
        "label": "Generó una ocasión",
        "short_label": "Ocasión +",
        "polarity": "positive",
        "rating_delta": 0.15,
    },
    "goal_created": {
        "label": "Intervino de forma decisiva en un gol",
        "short_label": "Gol +",
        "polarity": "positive",
        "rating_delta": 0.28,
    },
    "goal_prevented": {
        "label": "Evitó un gol",
        "short_label": "Evitó gol",
        "polarity": "positive",
        "rating_delta": 0.35,
    },
    "chance_conceded": {
        "label": "El error generó una ocasión rival",
        "short_label": "Ocasión rival",
        "polarity": "negative",
        "rating_delta": -0.25,
    },
    "goal_conceded": {
        "label": "El error terminó en gol rival",
        "short_label": "Costó gol",
        "polarity": "negative",
        "rating_delta": -0.55,
    },
}

MATCH_IMPACT_REASONS = {
    "lost_mark": "Pérdida de marca",
    "turnover": "Pérdida de balón",
    "failed_dribble": "Regate fallado",
    "failed_clearance": "Despeje fallado",
    "technical_error": "Error técnico",
    "goalkeeper_error": "Error del portero",
    "decisive_action": "Acción decisiva",
    "other": "Otra",
}


def normalize_match_impact(code, reason=""):
    code = str(code or "").strip().lower()
    if code not in MATCH_IMPACT_OPTIONS:
        return None
    reason = str(reason or "").strip().lower()
    if reason not in MATCH_IMPACT_REASONS:
        reason = ""
    option = MATCH_IMPACT_OPTIONS[code]
    return {
        "code": code,
        "label": option["label"],
        "short_label": option["short_label"],
        "polarity": option["polarity"],
        "rating_delta": float(option["rating_delta"]),
        "reason": reason,
        "reason_label": MATCH_IMPACT_REASONS.get(reason, ""),
    }


def match_event_impact(event):
    raw_data = getattr(event, "raw_data", None)
    if not isinstance(raw_data, dict):
        return None
    stored = raw_data.get("impact")
    if not isinstance(stored, dict):
        return None
    return normalize_match_impact(stored.get("code"), stored.get("reason"))

