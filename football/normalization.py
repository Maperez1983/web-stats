import re
import unicodedata

from .event_taxonomy import normalize_label


POSITION_CHOICES = [
    ("POR", "Portero"),
    ("DFC", "Defensa central"),
    ("LD", "Lateral derecho"),
    ("LI", "Lateral izquierdo"),
    ("CARRILERO D", "Carrilero derecho"),
    ("CARRILERO I", "Carrilero izquierdo"),
    ("MCD", "Mediocentro defensivo"),
    ("MC", "Mediocentro"),
    ("INTERIOR D", "Interior derecho"),
    ("INTERIOR I", "Interior izquierdo"),
    ("MP", "Mediapunta"),
    ("ED", "Extremo derecho"),
    ("EI", "Extremo izquierdo"),
    ("SD", "Segundo delantero"),
    ("DC", "Delantero centro"),
]

FOOT_CHOICES = [
    ("derecho", "Derecho"),
    ("izquierdo", "Izquierdo"),
    ("ambidiestro", "Ambidiestro"),
]

SKIN_TONE_CHOICES = [
    ("light", "Clara"),
    ("medium", "Media"),
    ("dark", "Oscura"),
]

_POSITION_STORAGE_MAP = {
    "por": "POR",
    "gk": "POR",
    "pt": "POR",
    "portero": "POR",
    "guardameta": "POR",
    "dfc": "DFC",
    "defensa central": "DFC",
    "central": "DFC",
    "defensa derecho": "LD",
    "defensa derecha": "LD",
    "ld": "LD",
    "lateral derecho": "LD",
    "lateral d": "LD",
    "carril derecho": "LD",
    "defensa izquierdo": "LI",
    "defensa izquierda": "LI",
    "li": "LI",
    "lateral izquierdo": "LI",
    "lateral i": "LI",
    "carril izquierdo": "LI",
    "mcd": "MCD",
    "mediocentro defensivo": "MCD",
    "pivote": "MCD",
    "mc": "MC",
    "medio centro": "MC",
    "mediocentro": "MC",
    "interior d": "INTERIOR D",
    "interior derecho": "INTERIOR D",
    "id": "INTERIOR D",
    "interior i": "INTERIOR I",
    "interior izquierdo": "INTERIOR I",
    "ii": "INTERIOR I",
    "mp": "MP",
    "media punta": "MP",
    "mediapunta": "MP",
    "ed": "ED",
    "extremo derecho": "ED",
    "ei": "EI",
    "extremo izquierdo": "EI",
    "sd": "SD",
    "segundo delantero": "SD",
    "dc": "DC",
    "delantero": "DC",
    "delantero centro": "DC",
    "punta": "DC",
    "carrilero d": "CARRILERO D",
    "carrilero derecho": "CARRILERO D",
    "carrilero i": "CARRILERO I",
    "carrilero izquierdo": "CARRILERO I",
}

_FOOT_STORAGE_MAP = {
    "right": "derecho",
    "derecho": "derecho",
    "r": "derecho",
    "left": "izquierdo",
    "izquierdo": "izquierdo",
    "l": "izquierdo",
    "both": "ambidiestro",
    "ambidiestro": "ambidiestro",
}


def _compact_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _split_title_token(token: str, *, preserve_acronyms: bool = False) -> str:
    text = _compact_text(token)
    if not text:
        return ""
    normalized = normalize_label(text)
    if text.isupper() and len(text) <= 2:
        return text.upper()
    if re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?", text.upper()):
        return text.upper()
    if preserve_acronyms:
        if "." in text and len(text) <= 6:
            return text.upper()
        if text.isupper() and len(text) <= 4:
            return text.upper()
        if normalized in {"cd", "cf", "fc", "ud", "sd", "cp", "ad", "rcd", "ud"}:
            return text.upper()
    if any(ch.isdigit() for ch in text):
        return text
    return text.title()


def normalize_person_name(value: object, *, preserve_acronyms: bool = False) -> str:
    text = _compact_text(value)
    if not text:
        return ""
    return " ".join(_split_title_token(token, preserve_acronyms=preserve_acronyms) for token in text.split(" "))


def normalize_position_value(value: object) -> str:
    text = _compact_text(value)
    if not text:
        return ""
    normalized = normalize_label(text)
    compact = normalized.replace(" ", "")
    for key in (normalized, compact):
        mapped = _POSITION_STORAGE_MAP.get(key)
        if mapped:
            return mapped
    upper = text.upper()
    if len(upper) <= 6 and upper.replace(".", "").replace(" ", "").isalnum():
        return upper
    return text.title()


def normalize_foot_value(value: object) -> str:
    text = _compact_text(value)
    if not text:
        return ""
    normalized = normalize_label(text)
    compact = normalized.replace(" ", "")
    for key in (normalized, compact):
        mapped = _FOOT_STORAGE_MAP.get(key)
        if mapped:
            return mapped
    return ""


def normalize_player_record(player):
    changed_fields = []
    for field_name, preserve_acronyms in (
        ("name", False),
        ("full_name", False),
        ("nickname", False),
        ("origin_team", True),
    ):
        current = getattr(player, field_name, "")
        normalized = normalize_person_name(current, preserve_acronyms=preserve_acronyms)
        if normalized != (current or ""):
            setattr(player, field_name, normalized)
            changed_fields.append(field_name)

    for field_name in ("preferred_position", "previous_season_position", "position"):
        current = getattr(player, field_name, "")
        normalized = normalize_position_value(current)
        if normalized != (current or ""):
            setattr(player, field_name, normalized)
            changed_fields.append(field_name)

    current_foot = getattr(player, "dominant_foot", "")
    normalized_foot = normalize_foot_value(current_foot)
    if normalized_foot != (current_foot or ""):
        setattr(player, "dominant_foot", normalized_foot)
        changed_fields.append("dominant_foot")

    return changed_fields


def normalize_scouting_target_record(target):
    changed_fields = []
    for field_name, preserve_acronyms in (
        ("subject_name", False),
        ("subject_team_name", True),
    ):
        current = getattr(target, field_name, "")
        normalized = normalize_person_name(current, preserve_acronyms=preserve_acronyms)
        if normalized != (current or ""):
            setattr(target, field_name, normalized)
            changed_fields.append(field_name)

    current_position = getattr(target, "position", "")
    normalized_position = normalize_position_value(current_position)
    if normalized_position != (current_position or ""):
        setattr(target, "position", normalized_position)
        changed_fields.append("position")

    current_foot = getattr(target, "dominant_foot", "")
    normalized_foot = normalize_foot_value(current_foot)
    if normalized_foot != (current_foot or ""):
        setattr(target, "dominant_foot", normalized_foot)
        changed_fields.append("dominant_foot")

    return changed_fields
