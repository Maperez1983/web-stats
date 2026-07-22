from django import template

from football.event_taxonomy import normalize_label
from football.normalization import normalize_person_name

register = template.Library()

_POSITION_DISPLAY_MAP = {
    "por": "Portero",
    "gk": "Portero",
    "pt": "Portero",
    "portero": "Portero",
    "guardameta": "Portero",
    "dfc": "Defensa central",
    "defensa central": "Defensa central",
    "defensacentral": "Defensa central",
    "defensa derecho": "Lateral derecho",
    "defensa derecha": "Lateral derecho",
    "ld": "Lateral derecho",
    "lateral derecho": "Lateral derecho",
    "lateral d": "Lateral derecho",
    "carril derecho": "Lateral derecho",
    "defensa izquierdo": "Lateral izquierdo",
    "defensa izquierda": "Lateral izquierdo",
    "li": "Lateral izquierdo",
    "lateral izquierdo": "Lateral izquierdo",
    "lateral i": "Lateral izquierdo",
    "carril izquierdo": "Lateral izquierdo",
    "mcd": "Mediocentro defensivo",
    "mediocentro defensivo": "Mediocentro defensivo",
    "mediocentrodefensivo": "Mediocentro defensivo",
    "pivote": "Mediocentro defensivo",
    "mc": "Mediocentro",
    "medio centro": "Mediocentro",
    "mediocentro": "Mediocentro",
    "interior d": "Interior derecho",
    "interiord": "Interior derecho",
    "id": "Interior derecho",
    "interior derecho": "Interior derecho",
    "interiorderecho": "Interior derecho",
    "interior i": "Interior izquierdo",
    "interiori": "Interior izquierdo",
    "ii": "Interior izquierdo",
    "interior izquierdo": "Interior izquierdo",
    "interiorizquierdo": "Interior izquierdo",
    "mp": "Mediapunta",
    "media punta": "Mediapunta",
    "mediapunta": "Mediapunta",
    "ed": "Extremo derecho",
    "extremo derecho": "Extremo derecho",
    "extremoderecho": "Extremo derecho",
    "ei": "Extremo izquierdo",
    "extremo izquierdo": "Extremo izquierdo",
    "extremoizquierdo": "Extremo izquierdo",
    "dc": "Delantero centro",
    "delantero centro": "Delantero centro",
    "delanterocentro": "Delantero centro",
    "sd": "Segundo delantero",
    "segundo delantero": "Segundo delantero",
    "segundodelantero": "Segundo delantero",
    "carrilero d": "Carrilero derecho",
    "carrilerod": "Carrilero derecho",
    "carrilero derecho": "Carrilero derecho",
    "carrilero i": "Carrilero izquierdo",
    "carrileroi": "Carrilero izquierdo",
    "carrilero izquierdo": "Carrilero izquierdo",
}


def _smart_title(value):
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    if text.isupper() and len(text) <= 4:
        return text
    return text.title()


@register.simple_tag(takes_context=True)
def qs_replace(context, /, **kwargs):
    """
    Reemplaza parámetros de querystring manteniendo el resto.

    Uso:
      <a href="?{% qs_replace tab='library' library_source='imported' lib_page=None %}">Importadas</a>
    """
    # Guardrail: si por error alguna plantilla usa `context=` como kwarg, Django pasaría
    # el contexto dos veces (posicional + kwarg). Con `context` como posicional-only (`/`)
    # evitamos el TypeError y simplemente ignoramos ese kwarg.
    try:
        if isinstance(kwargs, dict) and 'context' in kwargs:
            kwargs.pop('context', None)
    except Exception:
        pass
    request = context.get("request")
    if not request:
        return ""
    query = request.GET.copy()
    for key, value in (kwargs or {}).items():
        actual_key = 'context' if str(key) == 'context_' else str(key)
        if value is None:
            try:
                query.pop(actual_key)
            except KeyError:
                pass
            continue
        query[actual_key] = str(value)
    return query.urlencode()


@register.filter
def initials(value, count=2):
    text = " ".join(str(value or "").strip().split())
    if not text:
        return "?"
    words = [word for word in text.split(" ") if word]
    if not words:
        return "?"
    try:
        limit = max(1, int(count))
    except Exception:
        limit = 2
    if len(words) == 1:
        return words[0][:limit].upper()
    return "".join(word[0] for word in words[:limit]).upper()


@register.filter
def display_text(value):
    return normalize_person_name(value, preserve_acronyms=False)


@register.filter
def display_position(value):
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = normalize_label(text)
    compact = normalized.replace(" ", "")
    for key in (normalized, compact):
        if key in _POSITION_DISPLAY_MAP:
            return _POSITION_DISPLAY_MAP[key]
    return _smart_title(text)
