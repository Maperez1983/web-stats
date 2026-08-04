import logging
import re
import unicodedata

from .library_repositories import is_library_microcycle, library_repository_for_task
from .models import AiTrainerTaskIndex, AiTrainerTokenWeight


logger = logging.getLogger(__name__)

# Cuánto sube el peso de un concepto cada vez que el entrenador mete en una sesión REAL una
# tarea que lo trabaja. Bajo a propósito: la señal es abundante (una sesión por día) y lo que
# interesa es la tendencia de la temporada, no el último martes.
PESO_POR_USO = 0.35
LIMITE_PESO = 25.0


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


def _equipo_de_la_tarea(task):
    return getattr(getattr(getattr(task, 'session', None), 'microcycle', None), 'team', None)


def aprender_de_tarea_usada(task, *, team=None, delta=None):
    """Sube el peso de los conceptos de una tarea que el entrenador ha metido en una sesión.

    De dónde sale la señal importa: hasta ahora los pesos SOLO se movían desde dos botones de
    la pantalla IA-Trainer, así que con 288 tareas indexadas y una temporada de sesiones el
    sistema no había aprendido ni un dato (0 filas en AiTrainerTokenWeight el 2026-08-04).
    Lo que de verdad dice qué le gusta al entrenador es lo que acaba poniendo en el campo.

    Las tareas de la BIBLIOTECA no cuentan: guardar una plantilla no es decidir entrenarla.
    Devuelve el número de conceptos reforzados (0 si no procedía).
    """
    if not task:
        return 0
    microcycle = getattr(getattr(task, 'session', None), 'microcycle', None)
    if microcycle is None:
        return 0
    try:
        if is_library_microcycle(microcycle):
            return 0
    except Exception:
        logger.debug('No se pudo saber si el microciclo es de biblioteca', exc_info=True)
        return 0

    team = team or _equipo_de_la_tarea(task)
    if not team:
        return 0

    tokens = []
    indice = getattr(task, 'ai_trainer_index', None)
    if indice is not None and isinstance(getattr(indice, 'tokens', None), list):
        tokens = [str(t or '').strip().lower() for t in indice.tokens]
    if not tokens:
        texto = ' '.join(
            str(getattr(task, campo, '') or '')
            for campo in ('title', 'objective', 'coaching_points', 'confrontation_rules')
        )
        tokens = ai_trainer_tokenize(normalize_ai_trainer_text(texto), limit=32)

    tokens = [t for t in tokens if t][:24]
    if not tokens:
        return 0

    paso = float(PESO_POR_USO if delta is None else delta)
    reforzados = 0
    for token in tokens:
        clave = token[:64]
        try:
            fila, _ = AiTrainerTokenWeight.objects.get_or_create(team=team, workspace=None, token=clave)
            fila.weight = max(-LIMITE_PESO, min(LIMITE_PESO, float(fila.weight or 0.0) + paso))
            fila.save(update_fields=['weight', 'updated_at'])
            reforzados += 1
        except Exception:
            logger.debug('No se pudo reforzar el concepto %s', clave, exc_info=True)
    return reforzados
