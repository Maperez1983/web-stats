from django import template

register = template.Library()


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

