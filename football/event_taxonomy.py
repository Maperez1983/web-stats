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
DUEL_OFFENSIVE_KEYWORDS = {
    "regate",
    "regates",
    "dribbling",
    "dribble",
    "conduccion",
    "conducción",
    "encare",
    "1v1",
    "1x1",
}
DUEL_DEFENSIVE_KEYWORDS = {
    "duelo",
    "robo",
    "robado",
    "intercepción",
    "intervención",
    "entrada",
    "entradas",
    "recuperación",
    "recuperado",
    "presión",
    "presionado",
    "disputa",
}
DUEL_GENERIC_SUCCESS_KEYWORDS = {"ok", "ganado", "favorable", "exitoso", "completado"}
DUEL_GENERIC_FAIL_KEYWORDS = {"perdido", "fallado", "fallida", "falta", "error"}
DUEL_OFFENSIVE_SUCCESS_KEYWORDS = {"ok", "ganado", "superado", "exitoso", "completado"}
DUEL_OFFENSIVE_FAIL_KEYWORDS = {"perdido", "fallado", "fallida", "falta", "error", "interceptado", "robado"}
DUEL_DEFENSIVE_SUCCESS_KEYWORDS = {"ok", "ganado", "favorable", "robo", "recuper", "intercep", "entrada", "despeje"}
DUEL_DEFENSIVE_FAIL_KEYWORDS = {"perdido", "fallado", "fallida", "falta", "error", "superado", "regateado", "driblado"}

ZONE_MAP = {
    "porteria": "Portería",
    "porteria propia": "Portería",
    "area pequena": "Portería",
    "area pequeña": "Portería",
    "5 metros": "Portería",
    "meta": "Portería",
    "area propia": "Portería",
    "defensa izquierda": "Defensa Izquierda",
    "lateral izquierdo": "Defensa Izquierda",
    "carril izquierdo": "Defensa Izquierda",
    "costa izquierda": "Defensa Izquierda",
    "defensa izquierda centro": "Defensa Izquierda",
    "defensa central": "Defensa Centro",
    "defensa centro": "Defensa Centro",
    "central": "Defensa Centro",
    "zona central": "Defensa Centro",
    "defensa derecha": "Defensa Derecha",
    "lateral derecho": "Defensa Derecha",
    "carril derecho": "Defensa Derecha",
    "costa derecha": "Defensa Derecha",
    "medio izquierdo": "Medio Izquierda",
    "medio izquierda": "Medio Izquierda",
    "interior izquierdo": "Medio Izquierda",
    "interior izquierda": "Medio Izquierda",
    "costado izquierdo": "Medio Izquierda",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "mc": "Medio Centro",
    "interior": "Medio Centro",
    "medio derecho": "Medio Derecha",
    "medio derecha": "Medio Derecha",
    "interior derecho": "Medio Derecha",
    "interior derecha": "Medio Derecha",
    "costado derecho": "Medio Derecha",
    "media punta": "Ataque Centro",
    "pivote": "Medio Centro",
    "central ofensivo": "Medio Centro",
    "ataque izquierdo": "Ataque Izquierda",
    "extremo izquierdo": "Ataque Izquierda",
    "delantero izquierdo": "Ataque Izquierda",
    "ataque centro": "Ataque Centro",
    "frontal": "Ataque Centro",
    "ultimo tercio": "Ataque Centro",
    "último tercio": "Ataque Centro",
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
    "medio izquierdo": "Medio Izquierda",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "medio derecho": "Medio Derecha",
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
PASS_KEYWORDS = {
    'pase',
    'pases',
    'pase clave',
    'pase al hueco',
    'pase a la espalda',
    'cambio de orientacion',
    'cambio orientacion',
    'switch',
}
DRIBBLE_KEYWORDS = {'regate', 'regates', 'dribbling', 'dribble', 'conduccion', 'conducción'}
GOALKEEPER_SAVE_KEYWORDS = {'parada', 'paradas', 'atajada', 'atajadas', 'blocaje', 'blocajes'}
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
    zones.append(
        {
            'key': 'Portería',
            'label': 'Portería',
            'left': '0%',
            'top': '40%',
            'width': '8%',
            'height': '20%',
            'left_pct': 0,
            'top_pct': 40,
            'width_pct': 8,
            'height_pct': 20,
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


def is_goalkeeper_save_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, GOALKEEPER_SAVE_KEYWORDS)
        or contains_keyword(result, GOALKEEPER_SAVE_KEYWORDS)
        or contains_keyword(observation, GOALKEEPER_SAVE_KEYWORDS)
    )


def is_shot_attempt_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, SHOT_KEYWORDS)
        or is_goal_event(event_type, result=result, observation=observation)
        or contains_keyword(observation, SHOT_KEYWORDS)
    )


def is_shot_on_target_event(event_type, result=None, observation=None):
    if not is_shot_attempt_event(event_type, result=result, observation=observation):
        return False
    return (
        is_goal_event(event_type, result=result, observation=observation)
        or is_goalkeeper_save_event(event_type, result=result, observation=observation)
        or result_is_success(result)
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
    classification = classify_duel_event(event_type, result=None, observation=observation)
    return classification["is_duel"]


def duel_result_is_success(result):
    if not result:
        return False
    normalized = result.strip().lower()
    return any(keyword in normalized for keyword in DUEL_SUCCESS_KEYWORD)


def classify_duel_event(event_type, result=None, observation=None, zone=None):
    event_normalized = normalize_label(event_type)
    observation_normalized = normalize_label(observation)
    zone_normalized = normalize_label(zone)
    context_text = " ".join(part for part in [event_normalized, observation_normalized] if part).strip()
    result_text = " ".join(part for part in [normalize_label(result), observation_normalized] if part).strip()

    subtype = ""
    if any(keyword in context_text for keyword in DUEL_OFFENSIVE_KEYWORDS):
        subtype = "offensive"
    elif any(keyword in context_text for keyword in DUEL_DEFENSIVE_KEYWORDS):
        subtype = "defensive"
    elif "duelo" in zone_normalized:
        subtype = "generic"
    elif any(keyword in context_text for keyword in DUEL_EVENT_KEYWORDS):
        subtype = "generic"

    is_duel = bool(subtype)
    won = False
    if is_duel:
        if subtype == "offensive":
            success = any(keyword in result_text for keyword in DUEL_OFFENSIVE_SUCCESS_KEYWORDS) or result_is_success(result)
            failure = any(keyword in result_text for keyword in DUEL_OFFENSIVE_FAIL_KEYWORDS)
            won = success and not failure
        elif subtype == "defensive":
            success = any(keyword in result_text for keyword in DUEL_DEFENSIVE_SUCCESS_KEYWORDS) or result_is_success(result)
            failure = any(keyword in result_text for keyword in DUEL_DEFENSIVE_FAIL_KEYWORDS)
            won = success and not failure
        else:
            success = any(keyword in result_text for keyword in DUEL_GENERIC_SUCCESS_KEYWORDS) or duel_result_is_success(result)
            failure = any(keyword in result_text for keyword in DUEL_GENERIC_FAIL_KEYWORDS)
            won = success and not failure

    return {
        "is_duel": is_duel,
        "won": won,
        "subtype": subtype,
    }


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
    if 'porteria' in normalized or 'meta' in normalized:
        return 'Defensa'
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


def shots_needed_per_goal(shots, goals):
    shots_value = max(0, int(shots or 0))
    goals_value = max(0, int(goals or 0))
    if goals_value <= 0:
        return None
    return round(shots_value / goals_value, 2)


def calculate_importance_score(minutes, total_possible_minutes, successes, max_successes):
    minute_value = max(0, int(minutes or 0))
    possible_minutes = max(0, int(total_possible_minutes or 0))
    successes_value = max(0, int(successes or 0))
    max_success_value = max(0, int(max_successes or 0))

    availability_pct = round((minute_value / possible_minutes) * 100, 1) if possible_minutes else 0
    availability_pct = max(0, min(availability_pct, 100))
    success_volume_pct = round((successes_value / max_success_value) * 100, 1) if max_success_value else 0
    success_volume_pct = max(0, min(success_volume_pct, 100))
    importance_score = round((availability_pct * 0.6) + (success_volume_pct * 0.4), 1)
    importance_score = max(0, min(importance_score, 100))
    return {
        'availability_pct': availability_pct,
        'success_volume_pct': success_volume_pct,
        'importance_score': importance_score,
    }


def calculate_influence_score(minutes, successes, max_successes_per90):
    minute_value = max(0, int(minutes or 0))
    successes_value = max(0, int(successes or 0))
    max_success_per90_value = max(0, float(max_successes_per90 or 0))

    successes_per90 = round((successes_value / minute_value) * 90, 2) if minute_value else 0
    influence_pct = round((successes_per90 / max_success_per90_value) * 100, 1) if max_success_per90_value else 0
    influence_pct = max(0, min(influence_pct, 100))
    return {
        'successes_per90': successes_per90,
        'influence_score': influence_pct,
    }


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
    goals_per_match = round(goals / pj, 2)
    shots_per_goal = shots_needed_per_goal(shots, goals)

    if profile == 'striker':
        kpis = [
            {'label': 'Goles/PJ', 'value': f'{goals_per_match}'},
            {'label': 'Disparos/Gol', 'value': '-' if shots_per_goal is None else f'{shots_per_goal}'},
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
