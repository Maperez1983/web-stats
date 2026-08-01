"""
El GUION de una tarea: quién hay en el campo y por dónde se mueve.

Una tarea se dibuja en un lienzo Fabric, y eso está bien para EDITAR. Para REPRODUCIR el
movimiento (en la pizarra, en 3D, en el móvil del jugador, en un GIF o como imágenes del PDF) el
lienzo es un formato pésimo: `tactical_layout['timeline']` guarda hasta 24 pasos y **cada paso es
una copia entera del lienzo**, con los 22 jugadores repetidos con todos sus estilos. Son ~165 KB
por tarea, y son exactamente los que hacían que entrar en Entrenamiento tardara 5 segundos.

El guion guarda lo mismo de otra manera:

- Los **actores se declaran una vez** (quién es, de qué equipo, su color), no en cada paso.
- Las **posiciones van normalizadas 0..1** sobre el campo, no en píxeles del lienzo. Así el mismo
  guion se pinta igual en un móvil de 360 px, en un proyector y en un PDF a 296 dpi, sin
  recalcular nada y sin depender del tamaño con el que se dibujó.
- Cada paso solo dice **quién se mueve y adónde**.

El lienzo sigue siendo la fuente para editar; el guion se DERIVA de él al guardar. No sustituye a
nada todavía: `timeline` se conserva hasta que el guion esté verificado en las cuatro superficies.

Límites: los mismos que ya aplicaba el saneador del enlace público de simulación, para que las dos
rutas produzcan lo mismo y no vuelvan a divergir.
"""
from __future__ import annotations

import math

SCRIPT_VERSION = 1

MAX_STEPS = 40
MAX_ACTORS = 80
MAX_POINTS = 40
MAX_STEP_SECONDS = 20
MIN_STEP_SECONDS = 1

# Qué objetos del lienzo son "actores" (se mueven y cuentan en el guion). El resto —zonas,
# conos, formas, notas— es decorado: va en el campo, no en la coreografía.
TOKEN_KINDS = {
    'token', 'player', 'player_red', 'player_blue', 'player_local',
    'goalkeeper', 'goalkeeper_local',
}
BALL_KINDS = {'ball', 'ball_token', 'emoji_ball'}


def _num(value, default=0.0):
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _text(value, default=''):
    try:
        out = str(value or '').strip()
    except Exception:
        return default
    return out or default


def _object_kind(obj):
    """
    Tipo del objeto, con los mismos alias que usa el visor 3D (`normalizeObjectKindAlias`).

    Se replica aquí en vez de inventar otra clasificación: si el guion y el 3D no estuvieran de
    acuerdo en qué es un jugador, cada uno pintaría una cosa distinta a partir del mismo dibujo.
    """
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    raw = _text(data.get('kind') or data.get('token_kind') or obj.get('type')).lower()
    raw = raw.replace('-', '_')
    if raw.startswith('player') or raw.startswith('goalkeeper'):
        return 'token'
    if raw in BALL_KINDS:
        return 'ball'
    return raw


def _object_center(obj):
    """
    Centro del objeto en coordenadas del lienzo.

    Fabric guarda `left`/`top` respecto a su origen, que puede ser el centro o una esquina. Se
    replica el criterio de `objectCenter2d()` del visor 3D. No se aplica la rotación: para un
    objeto con origen centrado no mueve el centro, y los jugadores siempre lo tienen centrado.
    """
    width = _num(obj.get('width')) * _num(obj.get('scaleX'), 1.0)
    height = _num(obj.get('height')) * _num(obj.get('scaleY'), 1.0)
    left = _num(obj.get('left'))
    top = _num(obj.get('top'))
    origin_x = _text(obj.get('originX'), 'center').lower()
    origin_y = _text(obj.get('originY'), 'center').lower()
    if origin_x == 'left':
        left += width / 2.0
    elif origin_x == 'right':
        left -= width / 2.0
    if origin_y == 'top':
        top += height / 2.0
    elif origin_y == 'bottom':
        top -= height / 2.0
    return left, top


def _actor_uid(obj, index):
    """Identidad estable del actor entre pasos: sin ella no hay movimiento, hay parpadeo."""
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    for key in ('token_id', 'tokenId', 'playerId', 'player_id', 'layer_uid', 'uid', 'id'):
        value = _text(data.get(key))
        if value:
            return value[:80]
    # Sin identidad propia se usa la posición en la lista. Es frágil si el orden cambia, pero es
    # mejor que descartar el actor: al menos el paso se pinta.
    return f'obj{index}'


def _actor_from_object(obj, index):
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    kind = _object_kind(obj)
    if kind not in {'token', 'ball'}:
        return None
    color = _text(data.get('token_base_color')) or _text(obj.get('fill')) or '#2f6fd6'
    return {
        'uid': _actor_uid(obj, index),
        'kind': kind,
        'team': _text(data.get('token_team') or data.get('team'))[:12],
        'label': _text(data.get('playerNumber') or data.get('label'))[:6],
        'name': _text(data.get('playerName'))[:60],
        'color': color[:24],
    }


def _canvas_size(state, step):
    """Tamaño del lienzo del paso. Sin él no se puede normalizar y el paso se descarta."""
    width = _num(step.get('canvas_width')) or _num(state.get('width'))
    height = _num(step.get('canvas_height')) or _num(state.get('height'))
    return width, height


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _round_pos(value):
    # 4 decimales = ~1 cm en un campo de 105 m. Más precisión solo engorda el JSON.
    return round(value, 4)


def build_script(tactical_layout):
    """
    Deriva el guion a partir de lo que YA guarda la tarea.

    Prioriza `timeline` (los pasos dibujados). Si no hay pasos, produce un guion de un solo paso
    con el lienzo actual: así una tarea estática también tiene guion y las superficies no
    necesitan dos caminos distintos.

    Nunca lanza: si algo no cuadra devuelve un guion vacío y quien lo lea se comporta como hoy.
    """
    try:
        if not isinstance(tactical_layout, dict):
            return {}
        meta = tactical_layout.get('meta') if isinstance(tactical_layout.get('meta'), dict) else {}
        editor = meta.get('graphic_editor') if isinstance(meta.get('graphic_editor'), dict) else {}

        raw_steps = tactical_layout.get('timeline')
        if not isinstance(raw_steps, list) or not raw_steps:
            base_state = editor.get('canvas_state') if isinstance(editor.get('canvas_state'), dict) else {}
            if not isinstance(base_state.get('objects'), list):
                return {}
            raw_steps = [{
                'title': 'Único',
                'duration': 4,
                'canvas_state': base_state,
                'canvas_width': _num(editor.get('canvas_width')),
                'canvas_height': _num(editor.get('canvas_height')),
            }]

        actors_by_uid = {}
        steps = []
        for index, step in enumerate(raw_steps[:MAX_STEPS]):
            if not isinstance(step, dict):
                continue
            state = step.get('canvas_state')
            if not isinstance(state, dict):
                continue
            objects = state.get('objects')
            if not isinstance(objects, list):
                continue
            width, height = _canvas_size(state, step)
            if width <= 0 or height <= 0:
                continue

            routes = step.get('routes') if isinstance(step.get('routes'), dict) else {}
            moves = {}
            for obj_index, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    continue
                actor = _actor_from_object(obj, obj_index)
                if not actor:
                    continue
                uid = actor['uid']
                if uid not in actors_by_uid and len(actors_by_uid) < MAX_ACTORS:
                    actors_by_uid[uid] = actor
                if uid not in actors_by_uid:
                    continue
                cx, cy = _object_center(obj)
                start = [_round_pos(_clamp01(cx / width)), _round_pos(_clamp01(cy / height))]

                # Con recorrido dibujado, el recorrido ES el camino: no se le antepone la posición
                # actual. Hacerlo metía un punto de más y la ficha salía hacia atrás antes de
                # arrancar, porque el recorrido ya empieza donde está.
                # Sin recorrido, se guarda solo su posición y quien reproduce interpola hasta el
                # paso siguiente, que es lo que ya hace el visor 3D.
                route = routes.get(uid)
                route_points = []
                if isinstance(route, dict) and isinstance(route.get('points'), list):
                    for raw_point in route['points'][:MAX_POINTS]:
                        if not isinstance(raw_point, dict):
                            continue
                        px = _num(raw_point.get('x'), 0.0)
                        py = _num(raw_point.get('y'), 0.0)
                        route_points.append([_round_pos(_clamp01(px / width)), _round_pos(_clamp01(py / height))])
                moves[uid] = route_points if len(route_points) >= 2 else [start]

            if not moves:
                continue
            duration = int(_num(step.get('duration'), 3)) or 3
            steps.append({
                'title': _text(step.get('title'), f'Paso {index + 1}')[:80],
                'duration': max(MIN_STEP_SECONDS, min(duration, MAX_STEP_SECONDS)),
                'moves': moves,
                'ball': _text(step.get('ball_follow_uid'))[:80],
                'note': _text(step.get('note'))[:180],
            })

        if not steps:
            return {}

        return {
            'v': SCRIPT_VERSION,
            'pitch': {
                'preset': _text(meta.get('pitch_preset'), 'flat_2d')[:40],
                'orientation': _text(meta.get('pitch_orientation'), 'h')[:4],
            },
            'actors': list(actors_by_uid.values()),
            'steps': steps,
        }
    except Exception:
        return {}


def normalize_script(raw):
    """Sanea un guion que llega de fuera (cliente o import). Mismos límites que al derivarlo."""
    if not isinstance(raw, dict):
        return {}
    actors = []
    seen = set()
    for item in (raw.get('actors') if isinstance(raw.get('actors'), list) else [])[:MAX_ACTORS]:
        if not isinstance(item, dict):
            continue
        uid = _text(item.get('uid'))[:80]
        if not uid or uid in seen:
            continue
        seen.add(uid)
        actors.append({
            'uid': uid,
            'kind': _text(item.get('kind'), 'token')[:16],
            'team': _text(item.get('team'))[:12],
            'label': _text(item.get('label'))[:6],
            'name': _text(item.get('name'))[:60],
            'color': _text(item.get('color'), '#2f6fd6')[:24],
        })
    if not actors:
        return {}

    steps = []
    for index, item in enumerate((raw.get('steps') if isinstance(raw.get('steps'), list) else [])[:MAX_STEPS]):
        if not isinstance(item, dict):
            continue
        raw_moves = item.get('moves') if isinstance(item.get('moves'), dict) else {}
        moves = {}
        for uid, path in raw_moves.items():
            uid = _text(uid)[:80]
            if uid not in seen or not isinstance(path, list):
                continue
            points = []
            for point in path[:MAX_POINTS]:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                points.append([_round_pos(_clamp01(_num(point[0]))), _round_pos(_clamp01(_num(point[1])))])
            if points:
                moves[uid] = points
        if not moves:
            continue
        duration = int(_num(item.get('duration'), 3)) or 3
        steps.append({
            'title': _text(item.get('title'), f'Paso {index + 1}')[:80],
            'duration': max(MIN_STEP_SECONDS, min(duration, MAX_STEP_SECONDS)),
            'moves': moves,
            'ball': _text(item.get('ball'))[:80],
            'note': _text(item.get('note'))[:180],
        })
    if not steps:
        return {}

    pitch = raw.get('pitch') if isinstance(raw.get('pitch'), dict) else {}
    return {
        'v': SCRIPT_VERSION,
        'pitch': {
            'preset': _text(pitch.get('preset'), 'flat_2d')[:40],
            'orientation': _text(pitch.get('orientation'), 'h')[:4],
        },
        'actors': actors,
        'steps': steps,
    }


# Claves que NO viajan en la copia ligera: son el lienzo pesado (~165 KB por tarea) y solo las
# necesita el editor. Sacarlas es lo que permite que listados y fichas no des-diferan la columna.
_HEAVY_KEYS = ('tokens', 'timeline')
_HEAVY_META_KEYS = ('graphic_editor', 'original_version')


def build_layout_light(tactical_layout):
    """
    `task_layout_light` = el layout sin el lienzo pesado, con el guion ya calculado dentro.

    Vive aquí y no dentro de `SessionTask.save()` porque hay dos productores: el guardado normal
    y el comando de relleno. Con la lógica duplicada, una tarea rellenada por el comando y otra
    guardada por el editor acabarían con copias ligeras distintas — que es exactamente el problema
    que este módulo existe para evitar.
    """
    if not isinstance(tactical_layout, dict):
        return {}
    light = {k: v for k, v in tactical_layout.items() if k not in _HEAVY_KEYS}
    meta = light.get('meta')
    if isinstance(meta, dict):
        light['meta'] = {k: v for k, v in meta.items() if k not in _HEAVY_META_KEYS}
    try:
        script = build_script(tactical_layout)
    except Exception:
        script = None
    if script:
        light['script'] = script
    else:
        light.pop('script', None)
    return light
