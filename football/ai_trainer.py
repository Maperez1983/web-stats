import logging
import re
import unicodedata

from .library_repositories import library_repository_for_task
from .models import AiTrainerTaskIndex


logger = logging.getLogger(__name__)


def normalize_ai_trainer_text(value: str) -> str:
    raw = str(value or '')
    if not raw:
        return ''
    raw = unicodedata.normalize('NFKD', raw)
    raw = ''.join([c for c in raw if not unicodedata.combining(c)])
    raw = raw.lower()
    raw = raw.replace('_', ' ').replace('-', ' ')
    return ' '.join([chunk for chunk in raw.split() if chunk])


def ai_trainer_tokenize(text_norm: str, *, limit: int = 96) -> list:
    text = str(text_norm or '').strip().lower()
    if not text:
        return []
    try:
        parts = re.split(r'[^a-z0-9áéíóúüñ]+', text, flags=re.IGNORECASE)
    except Exception:
        parts = text.split()
    stop = {
        'para', 'pero', 'porque', 'como', 'cuando', 'donde', 'desde', 'hasta',
        'con', 'sin', 'sobre', 'entre', 'tras', 'ante', 'por', 'del', 'de', 'la', 'el', 'los', 'las', 'un', 'una',
        'y', 'o', 'u', 'a', 'en', 'al', 'se', 'su', 'sus', 'que', 'qué',
        'trabajar', 'mejorar', 'hacer', 'quiero', 'hoy',
    }
    out = []
    seen = set()
    for raw in parts:
        tok = str(raw or '').strip().lower()
        if not tok or len(tok) < 3 or tok in stop or tok.isdigit() or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= max(8, int(limit or 96)):
            break
    return out


def ai_trainer_index_task(task, *, team=None):
    if not task:
        return None
    team = team or getattr(getattr(getattr(task, 'session', None), 'microcycle', None), 'team', None)
    if not team:
        return None
    try:
        repo = library_repository_for_task(task)
    except Exception:
        logger.debug(
            'No se pudo resolver el repositorio de biblioteca de la tarea %s',
            getattr(task, 'id', None),
            exc_info=True,
        )
        repo = ''
    chunks = [
        str(getattr(task, 'title', '') or ''),
        str(getattr(task, 'objective', '') or ''),
        str(getattr(task, 'coaching_points', '') or ''),
        str(getattr(task, 'confrontation_rules', '') or ''),
    ]
    try:
        layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        analysis = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        summary = str(analysis.get('summary') or '')
        if summary:
            chunks.append(summary)
    except Exception:
        logger.debug(
            'No se pudo extraer el resumen tactico para indexar la tarea %s',
            getattr(task, 'id', None),
            exc_info=True,
        )
    content = ' '.join([c for c in chunks if str(c or '').strip()]).strip()[:20000]
    content_norm = normalize_ai_trainer_text(content)[:20000]
    tokens = ai_trainer_tokenize(content_norm, limit=128)
    try:
        idx, _ = AiTrainerTaskIndex.objects.update_or_create(
            task=task,
            defaults={
                'team': team,
                'repository': str(repo or '')[:32],
                'content': content,
                'content_norm': content_norm,
                'tokens': tokens,
            },
        )
        return idx
    except Exception:
        logger.exception('No se pudo indexar la tarea IA %s', getattr(task, 'id', None))
        return None
