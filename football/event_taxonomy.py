import re
import unicodedata


SUCCESS_RESULTS = {"ok", "ganado", "g", "ganó", "goles", "anotado", "marcado"}
DUEL_EVENT_KEYWORDS = {
    "duelo",
    "regate",
    "regates",
    "robo",
    "robado",
    "intercepción",
    "intervención",
    "entrada",
    "entradas",
    "recuperación",
    "recuperado",
    "falta cometida",
    "falta recibida",
    "presión",
    "presionado",
    "error forzado",
    "error",
    "disputa",
}
DUEL_SUCCESS_KEYWORD = {"ganado", "recuperado", "ok", "fortaleza", "favorable", "superado"}

ZONE_MAP = {
    "defensa izquierda": "Defensa Izquierda",
    "lateral izquierdo": "Defensa Izquierda",
    "carril izquierdo": "Defensa Izquierda",
    "costa izquierda": "Defensa Izquierda",
    "defensa izquierda centro": "Defensa Izquierda",
    "defensa central": "Defensa Centro",
    "central": "Defensa Centro",
    "zona central": "Defensa Centro",
    "defensa derecha": "Defensa Derecha",
    "lateral derecho": "Defensa Derecha",
    "carril derecho": "Defensa Derecha",
    "costa derecha": "Defensa Derecha",
    "medio izquierdo": "Medio Izquierdo",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "medio derecho": "Medio Derecho",
    "media punta": "Ataque Centro",
    "pivote": "Medio Centro",
    "central ofensivo": "Medio Centro",
    "ataque izquierdo": "Ataque Izquierda",
    "extremo izquierdo": "Ataque Izquierda",
    "delantero izquierdo": "Ataque Izquierda",
    "ataque centro": "Ataque Centro",
    "delantero centro": "Ataque Centro",
    "punta": "Ataque Centro",
    "ataque derecho": "Ataque Derecha",
    "delantero derecho": "Ataque Derecha",
    "extremo derecho": "Ataque Derecha",
    "delantero": "Ataque Centro",
    "atacante": "Ataque Centro",
    "delanztero": "Ataque Centro",
}
POSITION_MAP = {
    "defensa izquierda": "Defensa Izquierda",
    "lateral izquierdo": "Defensa Izquierda",
    "carril izquierdo": "Defensa Izquierda",
    "izquierda": "Defensa Izquierda",
    "defensa central": "Defensa Centro",
    "central": "Defensa Centro",
    "defensa derecha": "Defensa Derecha",
    "lateral derecho": "Defensa Derecha",
    "carril derecho": "Defensa Derecha",
    "derecha": "Defensa Derecha",
    "medio izquierdo": "Medio Izquierdo",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "medio derecho": "Medio Derecho",
    "pivote": "Medio Centro",
    "delantero izquierdo": "Ataque Izquierda",
    "ataque izquierdo": "Ataque Izquierda",
    "extremo izquierdo": "Ataque Izquierda",
    "delantero centro": "Ataque Centro",
    "ataque centro": "Ataque Centro",
    "delantero derecho": "Ataque Derecha",
    "ataque derecho": "Ataque Derecha",
    "extremo derecho": "Ataque Derecha",
    "punta": "Ataque Centro",
    "delantero": "Ataque Centro",
    "atacante": "Ataque Centro",
}
TERCIO_MAP = {
    "ataque": "Ataque",
    "ofensivo": "Ataque",
    "zona ataque": "Ataque",
    "finalización": "Ataque",
    "propia": "Defensa",
    "defensa": "Defensa",
    "defensivo": "Defensa",
    "construccion": "Construcción",
    "construcción": "Construcción",
    "medio": "Construcción",
    "progresión": "Construcción",
    "posesión": "Construcción",
    "control": "Construcción",
    "ataque centro": "Ataque",
    "ataque izquierdo": "Ataque",
}
STANDARD_TERCIO_LABELS = ['Ataque', 'Construcción', 'Defensa']
SHOT_KEYWORDS = {'tiro', 'remate', 'disparo', 'chuza', 'chute'}
PASS_KEYWORDS = {'pase', 'pases', 'pase clave', 'pase al hueco'}
DRIBBLE_KEYWORDS = {'regate', 'regates', 'dribbling', 'dribble', 'conduccion', 'conducción'}
GOAL_KEYWORDS = {'gol', 'goles', 'anotado', 'marcado', 'goal'}
ASSIST_KEYWORDS = {'asistencia', 'asist', 'pase gol', 'asiste'}
YELLOW_CARD_KEYWORDS = {'amarilla', 'tarjeta amarilla'}
RED_CARD_KEYWORDS = {'roja', 'tarjeta roja'}
SUBSTITUTION_KEYWORDS = {'sustitucion', 'sustitución', 'cambio'}
SUB_ENTRY_KEYWORDS = {'entrada', 'entrante', 'subida'}
SUB_EXIT_KEYWORDS = {'salida', 'saliente', 'bajada'}


def _build_field_zones():
    sections = [
        {'key': 'Defensa', 'label': 'Defensa', 'left_pct': 0, 'width_pct': 35},
        {'key': 'Medio', 'label': 'Medio', 'left_pct': 35, 'width_pct': 30},
        {'key': 'Ataque', 'label': 'Ataque', 'left_pct': 65, 'width_pct': 35},
    ]
    lanes = [
        {'suffix': 'Izquierda', 'top_pct': 0, 'height_pct': 33},
        {'suffix': 'Centro', 'top_pct': 33, 'height_pct': 34},
        {'suffix': 'Derecha', 'top_pct': 67, 'height_pct': 33},
    ]
    zones = []
    for section in sections:
        for lane in lanes:
            key = f"{section['key']} {lane['suffix']}"
            label = f"{section['label']} {lane['suffix']}"
            zones.append(
                {
                    'key': key,
                    'label': label,
                    'left': f"{section['left_pct']}%",
                    'top': f"{lane['top_pct']}%",
                    'width': f"{section['width_pct']}%",
                    'height': f"{lane['height_pct']}%",
                    'left_pct': section['left_pct'],
                    'top_pct': lane['top_pct'],
                    'width_pct': section['width_pct'],
                    'height_pct': lane['height_pct'],
                }
            )
    return zones


FIELD_ZONES = _build_field_zones()
FIELD_ZONE_KEYS = [zone['key'] for zone in FIELD_ZONES]


def normalize_label(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    filtered = "".join(ch for ch in normalized if ch.isalnum() or ch.isspace())
    return filtered.lower().strip()


def contains_keyword(value, keywords):
    normalized = normalize_label(value)
    return any(keyword in normalized for keyword in keywords)


def is_goal_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, GOAL_KEYWORDS)
        or contains_keyword(result, GOAL_KEYWORDS)
        or contains_keyword(observation, GOAL_KEYWORDS)
    )


def is_assist_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, ASSIST_KEYWORDS)
        or contains_keyword(result, ASSIST_KEYWORDS)
        or contains_keyword(observation, ASSIST_KEYWORDS)
    )


def is_yellow_card_event(event_type, result=None, zone=None):
    return (
        contains_keyword(event_type, YELLOW_CARD_KEYWORDS)
        or contains_keyword(result, YELLOW_CARD_KEYWORDS)
        or contains_keyword(zone, YELLOW_CARD_KEYWORDS)
    )


def is_red_card_event(event_type, result=None, zone=None):
    return (
        contains_keyword(event_type, RED_CARD_KEYWORDS)
        or contains_keyword(result, RED_CARD_KEYWORDS)
        or contains_keyword(zone, RED_CARD_KEYWORDS)
    )


def is_substitution_event(event_type, zone=None):
    return contains_keyword(event_type, SUBSTITUTION_KEYWORDS) or contains_keyword(zone, SUBSTITUTION_KEYWORDS)


def is_substitution_entry(event_type, result=None, zone=None):
    if not is_substitution_event(event_type, zone):
        return False
    return contains_keyword(result, SUB_ENTRY_KEYWORDS) or contains_keyword(zone, SUB_ENTRY_KEYWORDS)


def is_substitution_exit(event_type, result=None, zone=None):
    if not is_substitution_event(event_type, zone):
        return False
    return contains_keyword(result, SUB_EXIT_KEYWORDS) or contains_keyword(zone, SUB_EXIT_KEYWORDS)


def is_duel_event(event_type, observation=None):
    normalized = normalize_label(event_type)
    if not normalized:
        return False
    for keyword in DUEL_EVENT_KEYWORDS:
        if keyword in normalized:
            return True
    if observation:
        for keyword in DUEL_EVENT_KEYWORDS:
            if keyword in normalize_label(observation):
                return True
    return False


def duel_result_is_success(result):
    if not result:
        return False
    normalized = result.strip().lower()
    return any(keyword in normalized for keyword in DUEL_SUCCESS_KEYWORD)


def categorize_position(player_position, zone):
    normalized_position = normalize_label(player_position)
    normalized_zone = normalize_label(zone)
    for key, label in sorted(POSITION_MAP.items(), key=lambda item: -len(item[0])):
        if key in normalized_position or key in normalized_zone:
            return label
    return None


def zone_to_tercio(zone_label):
    normalized = normalize_label(zone_label)
    if not normalized:
        return ''
    if 'defensa' in normalized:
        return 'Defensa'
    if 'medio' in normalized or 'construcción' in normalized:
        return 'Construcción'
    if 'ataque' in normalized:
        return 'Ataque'
    return ''


def map_tercio(raw):
    normalized = normalize_label(raw)
    for key, label in TERCIO_MAP.items():
        if key in normalized:
            return label
    return None


def map_zone_label(zone):
    normalized = normalize_label(zone)
    for key, label in sorted(ZONE_MAP.items(), key=lambda item: -len(item[0])):
        if key in normalized:
            return label
    return None


def result_is_success(result):
    if not result:
        return False
    normalized = result.strip().lower()
    return normalized in SUCCESS_RESULTS


def min_or_none(current, candidate):
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)


def extract_round_number(value):
    if not value:
        return None
    match = re.search(r'(\d+)', str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def infer_player_profile(position):
    normalized = normalize_label(position)
    if not normalized:
        return 'midfielder'
    if 'portero' in normalized:
        return 'goalkeeper'
    if any(token in normalized for token in ('delantero', 'punta', 'nueve', '9')):
        return 'striker'
    if any(token in normalized for token in ('extremo', 'banda', 'winger')):
        return 'winger'
    if any(token in normalized for token in ('defensa', 'central', 'lateral', 'carrilero')):
        return 'defender'
    return 'midfielder'


def format_profile_label(profile):
    return {
        'goalkeeper': 'Portero',
        'defender': 'Defensa',
        'midfielder': 'Mediocampo',
        'winger': 'Extremo',
        'striker': 'Delantero',
    }.get(profile, 'Jugador')


def build_smart_kpis(stats):
    profile = infer_player_profile(stats.get('position') or '')
    pj = max(1, int(stats.get('pj', 0) or 0))
    success_rate = round((stats.get('successes', 0) / stats.get('total_actions', 0)) * 100, 1) if stats.get('total_actions') else 0
    shots = int(stats.get('shot_attempts', 0) or 0)
    goals = int(stats.get('goals', 0) or 0)
    duels_total = int(stats.get('duels_total', 0) or 0)
    duels_won = int(stats.get('duels_won', 0) or 0)
    duel_rate = round((duels_won / duels_total) * 100, 1) if duels_total else 0
    dribbles_total = int(stats.get('dribbles_attempted', 0) or 0)
    dribbles_won = int(stats.get('dribbles_completed', 0) or 0)
    dribble_rate = round((dribbles_won / dribbles_total) * 100, 1) if dribbles_total else 0
    passes_attempts = int(stats.get('pass_attempts', 0) or 0)
    passes_completed = int(stats.get('passes_completed', 0) or 0)
    pass_rate = round((passes_completed / passes_attempts) * 100, 1) if passes_attempts else 0
    conversion = round((goals / shots) * 100, 1) if shots else 0
    goals_per_match = round(goals / pj, 2)

    if profile == 'striker':
        kpis = [
            {'label': 'Goles/PJ', 'value': f'{goals_per_match}'},
            {'label': 'Gol/Tiro', 'value': f'{conversion}%'},
            {'label': 'Efectividad', 'value': f'{success_rate}%'},
        ]
    elif profile == 'winger':
        kpis = [
            {'label': 'Regates G/T', 'value': f'{dribbles_won}/{dribbles_total}'},
            {'label': 'Regate %', 'value': f'{dribble_rate}%'},
            {'label': 'Duelos %', 'value': f'{duel_rate}%'},
        ]
    elif profile == 'defender':
        kpis = [
            {'label': 'Duelos G/T', 'value': f'{duels_won}/{duels_total}'},
            {'label': 'Duelos %', 'value': f'{duel_rate}%'},
            {'label': 'Pase %', 'value': f'{pass_rate}%'},
        ]
    elif profile == 'midfielder':
        kpis = [
            {'label': 'Duelos G/T', 'value': f'{duels_won}/{duels_total}'},
            {'label': 'Pase %', 'value': f'{pass_rate}%'},
            {'label': 'Efectividad', 'value': f'{success_rate}%'},
        ]
    else:
        kpis = [
            {'label': 'Efectividad', 'value': f'{success_rate}%'},
            {'label': 'Duelos G/T', 'value': f'{duels_won}/{duels_total}'},
            {'label': 'Pase %', 'value': f'{pass_rate}%'},
        ]
    return profile, format_profile_label(profile), kpis
