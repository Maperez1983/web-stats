from functools import lru_cache
import unicodedata


def is_manual_event_source(source_file):
    normalized = (source_file or '').strip().lower()
    return normalized == 'admin-manual' or 'manual' in normalized


def event_signature(event):
    if is_manual_event_source(getattr(event, 'source_file', '')):
        return ('manual-event', getattr(event, 'id', None))

    # Live match actions are intentionally not deduplicated by minute/type:
    # repeated actions in the same minute can be legitimate football events.
    if (getattr(event, 'source_file', '') or '').strip() == 'registro-acciones':
        return ('registro-acciones', getattr(event, 'id', None))

    minute = event.minute
    action_type = event_signature_canon_text(event.event_type)
    if minute is not None:
        return (
            event.match_id,
            event.player_id,
            minute,
            action_type,
        )
    return (
        event.match_id,
        event.player_id,
        minute,
        action_type,
        event_signature_canon_text(event.result),
        event_signature_canon_text(event.zone),
        event_signature_canon_text(event.tercio),
        event_signature_canon_text(event.observation),
    )


@lru_cache(maxsize=8192)
def event_signature_canon_text(value):
    text = ' '.join(str(value or '').split())
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()
