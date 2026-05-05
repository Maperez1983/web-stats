from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """
    Reemplaza parámetros de querystring manteniendo el resto.

    Uso:
      <a href="?{% qs_replace tab='library' library_source='imported' lib_page=None %}">Importadas</a>
    """
    request = context.get("request")
    if not request:
        return ""
    query = request.GET.copy()
    for key, value in (kwargs or {}).items():
        if value is None:
            try:
                query.pop(key)
            except KeyError:
                pass
            continue
        query[str(key)] = str(value)
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
