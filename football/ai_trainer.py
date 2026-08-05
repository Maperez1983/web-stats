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


# Cada cuánto se reduce a la mitad lo aprendido. Sin esto los pesos sólo suben y en unos
# meses todo lo habitual toca el tope: el sistema deja de distinguir y "balón" acaba pesando
# como "basculación". Con esto, lo que entrenas ESTE mes manda sobre lo de octubre.
VIDA_MEDIA_DIAS = 60.0


def peso_con_antiguedad(weight, updated_at, *, hoy=None):
    """El peso que de verdad vale hoy, descontando lo viejo."""
    try:
        base = float(weight or 0.0)
    except Exception:
        return 0.0
    if not base or updated_at is None:
        return base
    try:
        from django.utils import timezone

        ahora = hoy or timezone.now()
        dias = max(0.0, (ahora - updated_at).total_seconds() / 86400.0)
        return base * (0.5 ** (dias / VIDA_MEDIA_DIAS))
    except Exception:
        return base


def apuntar_uso_en_la_tarea_de_biblioteca(task):
    """Suma un uso a la tarea de BIBLIOTECA de la que salió esta copia.

    La señal más honesta de que una tarea vale no es lo que diga su texto: es que el
    entrenador la haya llevado al campo. Cada copia guarda de cuál salió, así que aquí sólo
    hay que seguir el rastro. Devuelve el id de la tarea reforzada, o 0.
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
        return 0

    from .models import SessionTask

    origen = 0
    for fuente in ('task_layout_light', 'tactical_layout'):
        datos = getattr(task, fuente, None)
        meta = datos.get('meta') if isinstance(datos, dict) and isinstance(datos.get('meta'), dict) else {}
        try:
            origen = int(meta.get('library_source_task_id') or 0)
        except Exception:
            origen = 0
        if origen:
            break
    if not origen or origen == int(getattr(task, 'id', 0) or 0):
        return 0

    fecha = getattr(getattr(task, 'session', None), 'session_date', None)
    try:
        from django.db.models import F

        actualizadas = SessionTask.objects.filter(id=origen).update(
            veces_usada=F('veces_usada') + 1,
            usada_por_ultima_vez=fecha,
        )
        # Elegir una es descartar las otras que se propusieron con ella.
        try:
            cerrar_recomendaciones_de_la_sesion(getattr(task, 'session', None), origen)
        except Exception:
            logger.debug('No se pudieron cerrar las recomendaciones', exc_info=True)
        return origen if actualizadas else 0
    except Exception:
        logger.debug('No se pudo apuntar el uso en la tarea %s', origen, exc_info=True)
        return 0


# Cuánto baja el peso de lo que se propone y no se coge. Muy por debajo de lo que sube al
# usarla (0.35): que no te sirva HOY no significa que sea mala.
CASTIGO_POR_IGNORAR = 0.05


def apuntar_lo_propuesto(team, session, tareas):
    """Deja constancia de qué propuso el recomendador para esta sesión.

    Una fila por (sesión, tarea): si se vuelve a proponer se cuenta, no se duplica. Con esto
    se puede medir el acierto —hasta ahora los pesos del motor se ajustaban a ojo— y saber
    qué se enseñó y no se cogió.
    """
    if not team or not tareas:
        return 0
    from .models import AiTrainerRecomendacion

    apuntadas = 0
    for puesto, tarea in enumerate(tareas, start=1):
        try:
            fila, creada = AiTrainerRecomendacion.objects.get_or_create(
                session=session if getattr(session, 'id', None) else None,
                task=tarea,
                defaults={
                    'team': team,
                    'puesto': puesto,
                    'score': float(getattr(tarea, 'ai_trainer_score', 0) or 0),
                    'motivos': list(getattr(tarea, 'ai_trainer_reasons', []) or []),
                },
            )
            if not creada:
                fila.puesto = puesto
                fila.score = float(getattr(tarea, 'ai_trainer_score', 0) or 0)
                fila.motivos = list(getattr(tarea, 'ai_trainer_reasons', []) or [])
                fila.veces_propuesta = int(fila.veces_propuesta or 0) + 1
                fila.save(update_fields=['puesto', 'score', 'motivos', 'veces_propuesta', 'propuesta_en'])
            apuntadas += 1
        except Exception:
            logger.debug('No se pudo apuntar la recomendacion de la tarea %s', getattr(tarea, 'id', None), exc_info=True)
    return apuntadas


def cerrar_recomendaciones_de_la_sesion(session, task_origen_id):
    """Al elegir una tarea, cierra el resto de lo que se propuso para esa sesión.

    Es la señal NEGATIVA que faltaba: las tareas que se enseñaron junto a la elegida se vieron
    y se descartaron. Baja poco a propósito —que no valga hoy no la hace mala—, pero repetido
    a lo largo de una temporada es lo que separa lo que usas de lo que sólo suena parecido.
    """
    if session is None or not getattr(session, 'id', None):
        return 0
    from django.utils import timezone

    from .models import AiTrainerRecomendacion

    try:
        AiTrainerRecomendacion.objects.filter(session_id=session.id, task_id=task_origen_id).update(
            usada=True, usada_en=timezone.now()
        )
        descartadas = list(
            AiTrainerRecomendacion.objects.filter(session_id=session.id, usada=False).select_related('task')
        )
    except Exception:
        logger.debug('No se pudieron cerrar las recomendaciones de la sesion', exc_info=True)
        return 0

    for fila in descartadas:
        try:
            aprender_de_tarea_usada(fila.task, team=fila.team, delta=-CASTIGO_POR_IGNORAR, forzar=True)
        except Exception:
            logger.debug('No se pudo restar por descarte la tarea %s', fila.task_id, exc_info=True)
    return len(descartadas)


def _equipo_de_la_tarea(task):
    return getattr(getattr(getattr(task, 'session', None), 'microcycle', None), 'team', None)


def aprender_de_tarea_usada(task, *, team=None, delta=None, forzar=False):
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
        # `forzar` es para la señal de DESCARTE: ahí la tarea es justo la de biblioteca que se
        # propuso y no se cogió, así que hay que poder tocarla.
        if is_library_microcycle(microcycle) and not forzar:
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
