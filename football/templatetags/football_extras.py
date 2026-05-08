from django import template

register = template.Library()


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
