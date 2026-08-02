import re
import unicodedata


SUCCESS_RESULTS = {"ok", "ganado", "g", "ganó", "goles", "anotado", "marcado"}

# Disparos "a puerta" usados históricamente por el staff (ej: "AP") o nuevas variantes.
SHOT_ON_TARGET_RESULTS = {
    "ap",
    "a puerta",
    "apuerta",
    "a_puerta",
    "a-puerta",
    "a/p",
    "a p",
    "a- p",
    "a",
}
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
DUEL_AERIAL_KEYWORDS = {
    "aereo",
    "aéreo",
    "balon aereo",
    "balón aéreo",
    "juego aereo",
    "juego aéreo",
    "duelo aereo",
    "duelo aéreo",
    "disputa aerea",
    "disputa aérea",
    "cabeza",
    "cabezazo",
    "remate de cabeza",
}

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
KEY_PASS_KEYWORDS = {'pase clave', 'ultimo pase', 'último pase', 'key pass'}
DRIBBLE_KEYWORDS = {'regate', 'regates', 'dribbling', 'dribble', 'conduccion', 'conducción'}
GOALKEEPER_SAVE_KEYWORDS = {'parada', 'paradas', 'atajada', 'atajadas', 'blocaje', 'blocajes'}
GOAL_KEYWORDS = {'gol', 'goles', 'anotado', 'marcado', 'goal'}
ASSIST_KEYWORDS = {'asistencia', 'asist', 'pase gol', 'asiste'}
YELLOW_CARD_KEYWORDS = {'amarilla', 'tarjeta amarilla'}
RED_CARD_KEYWORDS = {'roja', 'tarjeta roja'}
SUBSTITUTION_KEYWORDS = {'sustitucion', 'sustitución', 'cambio'}
SUB_ENTRY_KEYWORDS = {
    'entrada',
    'entrante',
    'subida',
    'entra',
    'entrar',
    'ingresa',
    'ingresar',
    'in',
}
SUB_EXIT_KEYWORDS = {
    'salida',
    'saliente',
    'bajada',
    'sale',
    'salir',
    'retira',
    'retirado',
    'out',
}


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
    normalized_result = normalize_label(result)
    return (
        is_goal_event(event_type, result=result, observation=observation)
        or is_goalkeeper_save_event(event_type, result=result, observation=observation)
        or normalized_result in SHOT_ON_TARGET_RESULTS
        or result_is_success(result)
    )


def is_assist_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, ASSIST_KEYWORDS)
        or contains_keyword(result, ASSIST_KEYWORDS)
        or contains_keyword(observation, ASSIST_KEYWORDS)
    )


def is_key_pass_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, KEY_PASS_KEYWORDS)
        or contains_keyword(result, KEY_PASS_KEYWORDS)
        or contains_keyword(observation, KEY_PASS_KEYWORDS)
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
    is_aerial = False
    if is_duel:
        # “Aéreo” es una dimensión transversal (puede ser ofensivo/defensivo/genérico).
        # Lo inferimos por texto del evento/observación/zona.
        is_aerial = any(keyword in context_text for keyword in DUEL_AERIAL_KEYWORDS) or any(
            keyword in zone_normalized for keyword in DUEL_AERIAL_KEYWORDS
        )
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
        "aerial": is_aerial,
    }


# --- Taxonomía tipada (Fase 1) ---
# Cada acción del registro se mapea a UNO de estos tipos canónicos y se guarda en raw_data["kind"]
# al crear el MatchEvent. Así los lectores pueden preferir un tipo estable en vez de re-clasificar
# por texto libre (frágil ante etiquetas nuevas). Los eventos antiguos siguen funcionando por texto.
CANONICAL_EVENT_KINDS = (
    "goal",
    "assist",
    "key_pass",
    "shot_on_target",
    "shot",
    "dribble",
    "duel",
    "pass",
    "save",
    "yellow_card",
    "red_card",
    "substitution_in",
    "substitution_out",
    "substitution",
    "other",
)


def event_kind(event):
    """Tipo canónico de un MatchEvent: fuente ÚNICA de clasificación. Preferencia: (1) columna
    `kind` (Fase 4), (2) raw_data['kind'] (Fase 1), (3) derivar del texto (datos antiguos).
    Siempre devuelve un tipo válido -> nunca falla."""
    try:
        col = str(getattr(event, "kind", "") or "").strip().lower()
        if col in CANONICAL_EVENT_KINDS:
            return col
    except Exception:
        pass
    try:
        raw = getattr(event, "raw_data", None)
        if isinstance(raw, dict):
            stored = str(raw.get("kind") or "").strip().lower()
            if stored in CANONICAL_EVENT_KINDS:
                return stored
    except Exception:
        pass
    return canonical_event_kind(
        getattr(event, "event_type", None),
        getattr(event, "result", None),
        getattr(event, "zone", None),
        getattr(event, "observation", None),
    )


def canonical_event_kind(event_type, result=None, zone=None, observation=None):
    """Devuelve UN tipo canónico (de CANONICAL_EVENT_KINDS) para una acción, reutilizando los
    detectores de texto existentes, en orden de especificidad: roja antes que amarilla (la roja
    '(2ª amarilla)' contiene ambas), gol antes que tiro/parada, asistencia/pase clave antes que
    pase genérico. Clasificación CENTRALIZADA: el registro la persiste en raw_data['kind']."""
    et, res, zn, obs = event_type, result, zone, observation
    if is_red_card_event(et, res, zn):
        return "red_card"
    if is_yellow_card_event(et, res, zn):
        return "yellow_card"
    if is_substitution_entry(et, res, zn):
        return "substitution_in"
    if is_substitution_exit(et, res, zn):
        return "substitution_out"
    if is_substitution_event(et, zn):
        return "substitution"
    if is_goal_event(et, res, obs):
        return "goal"
    if is_goalkeeper_save_event(et, res, obs):
        return "save"
    if is_assist_event(et, res, obs):
        return "assist"
    if is_key_pass_event(et, res, obs):
        return "key_pass"
    if is_shot_on_target_event(et, res, obs):
        return "shot_on_target"
    if is_shot_attempt_event(et, res, obs):
        return "shot"
    if contains_keyword(et, DRIBBLE_KEYWORDS) or contains_keyword(res, DRIBBLE_KEYWORDS):
        return "dribble"
    if is_duel_event(et, obs):
        return "duel"
    if contains_keyword(et, PASS_KEYWORDS) or contains_keyword(res, PASS_KEYWORDS):
        return "pass"
    return "other"


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


def event_result_is_success(event_type, result):
    """Resultado efectivo de una acción, protegiendo datos históricos contradictorios."""
    event_label = normalize_label(event_type)
    negative_execution = any(
        label in event_label
        for label in (
            "perdida forzada",
            "error forzado",
            "perdida no forzada",
            "error no forzado",
        )
    )
    return result_is_success(result) and not negative_execution


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


def calculate_influence_score(
    minutes,
    successes,
    goals,
    assists,
    key_passes_completed,
    max_decisive_actions_per90,
    normalization_minutes=90,
):
    minute_value = max(0, int(minutes or 0))
    successes_value = max(0, int(successes or 0))
    goals_value = max(0, int(goals or 0))
    assists_value = max(0, int(assists or 0))
    key_passes_value = max(0, int(key_passes_completed or 0))
    max_decisive_actions_per90_value = max(0, float(max_decisive_actions_per90 or 0))

    try:
        norm_minutes = max(1, int(normalization_minutes or 90))
    except Exception:
        norm_minutes = 90

    successes_per90 = round((successes_value / minute_value) * norm_minutes, 2) if minute_value else 0
    decisive_actions = successes_value + (goals_value * 6) + (assists_value * 4) + (key_passes_value * 2)
    decisive_actions_per90 = round((decisive_actions / minute_value) * norm_minutes, 2) if minute_value else 0
    influence_pct = (
        round((decisive_actions_per90 / max_decisive_actions_per90_value) * 100, 1)
        if max_decisive_actions_per90_value
        else 0
    )
    influence_pct = max(0, min(influence_pct, 100))
    return {
        'successes_per90': successes_per90,
        'decisive_actions_per90': decisive_actions_per90,
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
    if normalized in {'por', 'gk'} or 'portero' in normalized:
        return 'goalkeeper'
    if normalized in {'dc', 'sd'} or any(token in normalized for token in ('delantero', 'punta', 'nueve', '9')):
        return 'striker'
    if normalized in {'ed', 'ei'} or any(token in normalized for token in ('extremo', 'banda', 'winger')):
        return 'winger'
    if normalized in {'dfc', 'ld', 'li'} or any(token in normalized for token in ('defensa', 'central', 'lateral', 'carrilero')):
        return 'defender'
    if normalized in {'mcd', 'mc', 'mp'} or 'interior' in normalized:
        return 'midfielder'
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
    assists = int(stats.get('assists', 0) or 0)
    goalkeeper_saves = int(stats.get('goalkeeper_saves', 0) or 0)
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

    if profile == 'goalkeeper':
        kpis = [
            {'label': 'Paradas', 'value': f'{goalkeeper_saves}'},
            {'label': 'Paradas/PJ', 'value': f'{round(goalkeeper_saves / pj, 2)}'},
            {'label': 'Efectividad', 'value': f'{success_rate}%'},
        ]
    elif profile == 'striker':
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
    if assists > 0:
        kpis = [{'label': 'Asistencias', 'value': f'{assists}'}] + [
            item for item in kpis if item.get('label') != 'Asistencias'
        ]
        kpis = kpis[:3]
    return profile, format_profile_label(profile), kpis
