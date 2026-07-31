"""
Qué se ha ENTRENADO en la semana (bloque de entrenamiento del informe de microciclo).

El informe ya contaba quién vino: asistencia, multas e incidencias. Lo que faltaba es qué se
trabajó y cuánto: minutos por jugador, reparto por bloque, contenidos de la semana y cómo va la
cosa respecto a semanas anteriores.

De dónde salen los datos, y por qué de ahí: al confirmar una sesión se crea una fila de
`SessionTaskParticipation` por cada jugador y tarea, y los minutos de la tarea son
`SessionTask.duration_minutes`. Es decir, esto se rellena SOLO con el uso normal del programa.
La otra fuente posible (RPE y bienestar de `PlayerPhysicalMetric`) exige que alguien apunte a
diario y hoy está vacía, así que no se usa aquí: un informe que sale en blanco no informa.

Va en su propio módulo y no dentro de views.py a propósito: ese fichero pasa de las 85.000 líneas
y es donde chocan todas las ramas.
"""
from __future__ import annotations

from django.db.models import Sum

from .models import (
    SessionTask,
    SessionTaskParticipation,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
)

# Cuántas semanas se comparan hacia atrás en la tendencia (la actual incluida).
TREND_WEEKS = 6


def _task_meta(task):
    """`meta` de la tarea sin arrastrar el canvas (~165 KB por tarea)."""
    light = getattr(task, 'task_layout_light', None)
    if isinstance(light, dict) and isinstance(light.get('meta'), dict):
        return light['meta']
    layout = getattr(task, 'tactical_layout', None)
    if isinstance(layout, dict) and isinstance(layout.get('meta'), dict):
        return layout['meta']
    return {}


def _task_contents(task):
    """
    Contenidos que trabaja una tarea, como lista de etiquetas.

    MISMA fuente que la ficha y los PDF (`contents_label` en session_pdf._build_session_task_sheet):
    tipo de entrenamiento, fase de juego, principio y subprincipio del `meta`. Si aquí se leyera de
    otro sitio, el informe diría una cosa y la ficha otra sobre la misma tarea.
    """
    meta = _task_meta(task)
    labels = []
    for key in ('training_type', 'game_phase', 'principle', 'subprinciple'):
        text = str(meta.get(key) or '').strip()
        if text and text != '-':
            labels.append(text)
    if not labels:
        objective = str(getattr(task, 'objective', '') or '').strip()
        if objective and objective != '-':
            labels.append(objective)
    return labels


def _attendance_pct_for_sessions(session_ids):
    """% de asistencia (presentes + tarde) sobre los citables, excluyendo lesionados."""
    if not session_ids:
        return 0
    counts = {}
    for mark in TrainingSessionAttendance.objects.filter(session_id__in=session_ids).values_list('status', flat=True):
        counts[mark] = counts.get(mark, 0) + 1
    citable = (
        counts.get(TrainingSessionAttendance.STATUS_PRESENT, 0)
        + counts.get(TrainingSessionAttendance.STATUS_LATE, 0)
        + counts.get(TrainingSessionAttendance.STATUS_ABSENT, 0)
        + counts.get(TrainingSessionAttendance.STATUS_EXCUSED, 0)
    )
    if not citable:
        return 0
    ok = counts.get(TrainingSessionAttendance.STATUS_PRESENT, 0) + counts.get(TrainingSessionAttendance.STATUS_LATE, 0)
    return int(round(ok / citable * 100))


def build_training_block(team, microcycle, sessions, players_by_id):
    """
    Devuelve el contexto del bloque de entrenamiento. Nunca lanza: si algo falta, el bloque se
    apaga con `training_has_data = False` y el resto del informe sigue igual.
    """
    empty = {
        'training_has_data': False,
        'training_minutes_total': 0,
        'training_minutes_rows': [],
        'training_blocks': [],
        'training_contents': [],
        'training_focus': '',
        'training_focus_hits': 0,
        'training_trend': [],
        'training_tasks_count': 0,
    }
    if not team or not microcycle:
        return empty

    try:
        session_ids = [int(s['id']) for s in (sessions or []) if s.get('id')]
        if not session_ids:
            return empty

        tasks = list(
            SessionTask.objects.filter(session_id__in=session_ids, deleted_at__isnull=True)
            .defer('tactical_layout', 'preview_data_b64', 'cover_data_b64')
            .order_by('session_id', 'block', 'order', 'id')
        )
        if not tasks:
            return empty
        minutes_by_task = {int(t.id): int(getattr(t, 'duration_minutes', 0) or 0) for t in tasks}
        block_label_by_task = {int(t.id): t.get_block_display() for t in tasks}

        # --- Minutos y participación por jugador ------------------------------------------
        rows_by_player = {}
        participations = SessionTaskParticipation.objects.filter(
            session_task_id__in=list(minutes_by_task.keys())
        ).values_list('player_id', 'session_task_id')
        for player_id, task_id in participations:
            entry = rows_by_player.setdefault(int(player_id), {'minutes': 0, 'tasks': 0})
            entry['minutes'] += minutes_by_task.get(int(task_id), 0)
            entry['tasks'] += 1

        session_minutes_total = sum(minutes_by_task.values())
        minutes_rows = []
        for player_id, entry in rows_by_player.items():
            player = players_by_id.get(int(player_id))
            minutes_rows.append(
                {
                    'name': str(getattr(player, 'name', '') or f'Jugador {player_id}').strip(),
                    'number': getattr(player, 'number', None) or '',
                    'position': str(getattr(player, 'position', '') or '').strip(),
                    'minutes': entry['minutes'],
                    'tasks': entry['tasks'],
                    # Sobre el total de minutos de tarea de la semana: dice quién se ha quedado
                    # corto respecto a lo que se ha entrenado, no respecto a un ideal inventado.
                    'pct': int(round(entry['minutes'] / session_minutes_total * 100)) if session_minutes_total else 0,
                }
            )
        minutes_rows.sort(key=lambda r: (-r['minutes'], str(r['name']).lower()))

        # --- Reparto por bloque -------------------------------------------------------------
        by_block = {}
        for task in tasks:
            label = block_label_by_task.get(int(task.id)) or 'Sin bloque'
            entry = by_block.setdefault(label, {'label': label, 'minutes': 0, 'tasks': 0})
            entry['minutes'] += minutes_by_task.get(int(task.id), 0)
            entry['tasks'] += 1
        blocks = sorted(by_block.values(), key=lambda e: -e['minutes'])
        for entry in blocks:
            entry['pct'] = int(round(entry['minutes'] / session_minutes_total * 100)) if session_minutes_total else 0

        # --- Contenidos trabajados ----------------------------------------------------------
        by_content = {}
        for task in tasks:
            for label in _task_contents(task):
                key = label.lower()
                entry = by_content.setdefault(key, {'label': label, 'minutes': 0, 'tasks': 0})
                entry['minutes'] += minutes_by_task.get(int(task.id), 0)
                entry['tasks'] += 1
        contents = sorted(by_content.values(), key=lambda e: -e['minutes'])[:12]
        for entry in contents:
            entry['pct'] = int(round(entry['minutes'] / session_minutes_total * 100)) if session_minutes_total else 0

        # ¿Se está trabajando el foco declarado del microciclo? Comparación por texto, que es lo
        # que hay: el foco es un campo libre y los contenidos también.
        focus = str(
            getattr(microcycle, 'game_model_focus', '') or getattr(microcycle, 'objective', '') or ''
        ).strip()
        focus_hits = 0
        if focus:
            needle = focus.lower()
            for entry in by_content.values():
                label = entry['label'].lower()
                if label in needle or needle in label:
                    focus_hits += entry['tasks']

        # --- Comparativa entre semanas ------------------------------------------------------
        trend = []
        previous = list(
            TrainingMicrocycle.objects.filter(team=team, week_start__lte=microcycle.week_start)
            .exclude(week_start__year__lt=2001)  # fuera papelera (1970) y bandejas centinela (2000)
            .order_by('-week_start')[:TREND_WEEKS]
        )
        for mc in reversed(previous):
            mc_session_ids = list(
                TrainingSession.objects.filter(microcycle=mc).values_list('id', flat=True)
            )
            mc_minutes = (
                SessionTask.objects.filter(session_id__in=mc_session_ids, deleted_at__isnull=True).aggregate(
                    t=Sum('duration_minutes')
                ).get('t')
                or 0
            )
            trend.append(
                {
                    'week_start': mc.week_start,
                    'label': mc.week_start.strftime('%d/%m') if mc.week_start else '',
                    'sessions': len(mc_session_ids),
                    'minutes': int(mc_minutes),
                    'attendance': _attendance_pct_for_sessions(mc_session_ids),
                    'is_current': int(mc.id) == int(microcycle.id),
                }
            )
        peak = max([t['minutes'] for t in trend] or [0]) or 1
        for item in trend:
            item['bar_pct'] = int(round(item['minutes'] / peak * 100))

        return {
            'training_has_data': True,
            'training_minutes_total': session_minutes_total,
            'training_minutes_rows': minutes_rows,
            'training_blocks': blocks,
            'training_contents': contents,
            'training_focus': focus,
            'training_focus_hits': focus_hits,
            'training_trend': trend,
            'training_tasks_count': len(tasks),
        }
    except Exception:
        return empty
