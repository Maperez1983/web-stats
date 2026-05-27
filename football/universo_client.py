import base64
import json
import os
import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from football.event_taxonomy import normalize_label

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


def _env_path(name, default):
    value = os.getenv(name)
    return Path(value).expanduser() if value else Path(default)


UNIVERSO_STORAGE_STATE_PATH = _env_path(
    'RFAF_STORAGE_STATE_PATH',
    Path(settings.BASE_DIR) / 'data' / 'input' / 'rfaf_storage_state.json',
)
UNIVERSO_API_TIMEOUT_SECONDS = max(1, int(os.getenv('UNIVERSO_API_TIMEOUT_SECONDS', '8') or 8))


def _parse_int_safe(value, default=0):
    try:
        return int(str(value).strip() or 0)
    except Exception:
        return default


def jwt_exp_timestamp(token: str) -> float:
    raw = str(token or '').strip()
    if not raw or '.' not in raw:
        return 0.0
    try:
        parts = raw.split('.')
        if len(parts) < 2:
            return 0.0
        payload_b64 = parts[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
        payload = json.loads(decoded.decode('utf-8'))
        exp = payload.get('exp')
        return float(exp or 0.0) if exp else 0.0
    except Exception:
        return 0.0


def load_universo_access_token_from_storage_state() -> tuple[str, float]:
    storage_path = UNIVERSO_STORAGE_STATE_PATH
    if not storage_path.exists():
        return '', 0.0
    try:
        payload = json.loads(storage_path.read_text(encoding='utf-8'))
    except Exception:
        return '', 0.0
    for cookie in payload.get('cookies') or []:
        if not isinstance(cookie, dict):
            continue
        if str(cookie.get('name') or '').strip() != 'access_token':
            continue
        token = str(cookie.get('value') or '').strip()
        try:
            expires = float(cookie.get('expires') or 0.0) or 0.0
        except Exception:
            expires = 0.0
        return token, expires
    return '', 0.0


def fetch_universo_access_token_via_login() -> tuple[str, float, str]:
    if requests is None:
        return '', 0.0, 'requests no disponible'
    username = str(os.getenv('UNIVERSO_RFAF_USER', '') or os.getenv('RFAF_USER', '') or '').strip()
    password = str(os.getenv('UNIVERSO_RFAF_PASS', '') or os.getenv('RFAF_PASS', '') or '').strip()
    if not username or not password:
        return '', 0.0, 'Faltan UNIVERSO_RFAF_USER/UNIVERSO_RFAF_PASS (o RFAF_USER/RFAF_PASS)'
    url = 'https://www.universorfaf.es/api/login'
    headers = {
        'Accept': 'application/json',
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        'Origin': 'https://www.universorfaf.es',
        'Referer': 'https://www.universorfaf.es/login',
    }
    response = None
    try:
        response = requests.post(
            url,
            headers=headers,
            files={'email': (None, username), 'password': (None, password)},
            timeout=UNIVERSO_API_TIMEOUT_SECONDS,
        )
    except Exception:
        response = None
    if response is None:
        try:
            response = requests.post(
                url,
                headers=headers,
                data={'email': username, 'password': password},
                timeout=UNIVERSO_API_TIMEOUT_SECONDS,
            )
        except Exception:
            return '', 0.0, 'Error de red al hacer login'
    if not getattr(response, 'ok', False):
        try:
            details = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        except Exception:
            details = ''
        return '', 0.0, f'Login HTTP {getattr(response, "status_code", "")} {details}'.strip()
    try:
        payload = response.json()
    except Exception:
        return '', 0.0, 'Login no devolvió JSON'
    if not isinstance(payload, dict):
        return '', 0.0, 'Login devolvió formato inesperado'
    token = str(payload.get('token') or payload.get('access_token') or '').strip()
    if not token:
        return '', 0.0, 'Login OK pero sin token'
    return token, jwt_exp_timestamp(token), ''


def load_universo_access_token():
    memo = getattr(load_universo_access_token, '_memo', None)
    now_ts = timezone.now().timestamp()
    if isinstance(memo, dict):
        token = str(memo.get('token') or '').strip()
        exp_ts = float(memo.get('expires') or 0.0) if memo.get('expires') else 0.0
        if token and (not exp_ts or exp_ts - 60 > now_ts):
            return token

    token, exp_ts = load_universo_access_token_from_storage_state()
    if token and (not exp_ts or exp_ts - 60 > now_ts):
        load_universo_access_token._memo = {'token': token, 'expires': exp_ts, 'source': 'storage_state', 'error': ''}
        return token

    env_token = str(os.getenv('UNIVERSO_RFAF_ACCESS_TOKEN', '') or os.getenv('RFAF_ACCESS_TOKEN', '') or '').strip()
    if env_token:
        env_exp = jwt_exp_timestamp(env_token)
        if not env_exp or env_exp - 60 > now_ts:
            load_universo_access_token._memo = {'token': env_token, 'expires': env_exp, 'source': 'env', 'error': ''}
            return env_token

    token, exp_ts, error = fetch_universo_access_token_via_login()
    if token:
        load_universo_access_token._memo = {'token': token, 'expires': exp_ts, 'source': 'api_login', 'error': ''}
        return token
    if error:
        load_universo_access_token._memo = {'token': '', 'expires': 0.0, 'source': 'api_login', 'error': error}
    return ''


def load_universo_access_token_expires() -> float:
    memo = getattr(load_universo_access_token, '_memo', None)
    if isinstance(memo, dict) and memo.get('token'):
        try:
            return float(memo.get('expires') or 0.0) or 0.0
        except Exception:
            return 0.0
    _, exp_ts = load_universo_access_token_from_storage_state()
    if exp_ts:
        return float(exp_ts) or 0.0
    env_token = str(os.getenv('UNIVERSO_RFAF_ACCESS_TOKEN', '') or os.getenv('RFAF_ACCESS_TOKEN', '') or '').strip()
    if env_token:
        return jwt_exp_timestamp(env_token)
    return 0.0


def universo_api_post(endpoint, data=None):
    if requests is None:
        return {}
    token = load_universo_access_token()
    if not token:
        return {}
    url = f'https://www.universorfaf.es/api/novanet/{endpoint.lstrip("/")}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': '2j-football-intelligence/1.0',
    }
    try:
        response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
        if getattr(response, 'status_code', None) in (401, 403):
            load_universo_access_token._memo = None
            token = load_universo_access_token()
            if not token:
                return {}
            headers['Authorization'] = f'Bearer {token}'
            response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def universo_internal_post(endpoint, data=None):
    if requests is None:
        return {}
    token = load_universo_access_token()
    if not token:
        return {}
    url = f'https://www.universorfaf.es/api/internal-data/{endpoint.lstrip("/")}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': '2j-football-intelligence/1.0',
    }
    try:
        response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_universo_live_seasons():
    payload = universo_api_post('competition/get-seassons')
    rows = payload.get('temporadas') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        payload = universo_api_post('competition/get-seasons')
        rows = payload.get('temporadas') if isinstance(payload, dict) else None
    return [row for row in (rows or []) if isinstance(row, dict)]


def fetch_universo_live_delegations():
    payload = universo_api_post('competition/get-delegations')
    rows = payload.get('delegaciones') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        payload = universo_api_post('competition/get-delegation')
        rows = payload.get('delegaciones') if isinstance(payload, dict) else None
    return [row for row in (rows or []) if isinstance(row, dict)]


def fetch_universo_live_competitions(delegation_id, season_id):
    delegation_id = str(delegation_id or '').strip()
    season_id = str(season_id or '').strip()
    if not delegation_id or not season_id:
        return []
    attempts = [
        {'id_delegacion': delegation_id, 'id_season': season_id},
        {'cod_delegacion': delegation_id, 'cod_temporada': season_id},
        {'id_delegacion': delegation_id, 'cod_temporada': season_id},
        {'cod_delegacion': delegation_id, 'id_season': season_id},
        {'id_delegation': delegation_id, 'id_season': season_id},
        {'id_delegation': delegation_id, 'season_id': season_id},
    ]
    payload = {}
    for data in attempts:
        payload = universo_api_post('competition/get-competitions', data)
        if isinstance(payload, dict) and payload.get('competiciones'):
            break
    return [row for row in (payload.get('competiciones') or []) if isinstance(row, dict)]


def fetch_universo_live_groups(competition_id):
    competition_id = str(competition_id or '').strip()
    if not competition_id:
        return []
    attempts = [
        {'id_competition': competition_id},
        {'id_competicion': competition_id},
        {'cod_competicion': competition_id},
        {'codigo_competicion': competition_id},
        {'competition_id': competition_id},
    ]
    payload = {}
    for data in attempts:
        payload = universo_api_post('competition/get-groups', data)
        if isinstance(payload, dict) and payload.get('grupos'):
            break
    return [row for row in (payload.get('grupos') or []) if isinstance(row, dict)]


def fetch_universo_live_classification(group_id):
    group_id = str(group_id or '').strip()
    if not group_id:
        return {}
    payload = universo_api_post('competition/get-classification', {'id_group': group_id})
    if isinstance(payload, dict) and payload.get('clasificacion'):
        return payload
    try:
        results = fetch_universo_live_results(group_id)
    except Exception:
        results = {}
    round_id = str((results or {}).get('jornada') or '').strip()
    if not round_id:
        try:
            for bucket in (results or {}).get('listado_jornadas') or []:
                if not isinstance(bucket, dict):
                    continue
                for row in bucket.get('jornadas') or []:
                    if not isinstance(row, dict):
                        continue
                    rid = str(row.get('codjornada') or row.get('codigo') or '').strip()
                    if rid:
                        round_id = rid
                        break
                if round_id:
                    break
        except Exception:
            pass
    if round_id:
        payload = universo_api_post('competition/get-classification', {'id_group': group_id, 'id_round': round_id})
        if isinstance(payload, dict) and payload.get('clasificacion'):
            return payload
    return payload if isinstance(payload, dict) else {}


def fetch_universo_live_results(group_id, round_id=''):
    payload = universo_api_post(
        'match/get-results',
        {'id_group': str(group_id or '').strip(), 'id_round': str(round_id or '').strip()},
    )
    return payload if isinstance(payload, dict) else {}


def fetch_universo_team_roster(team_code: str) -> list[dict]:
    code = str(team_code or '').strip()
    if not code:
        return []
    payload = universo_internal_post('teams/detail', {'cod_equipo': code})
    if not payload:
        raise ValueError(
            'No se pudo consultar Universo RFAF (sin sesión o token caducado). '
            'Regenera `data/input/rfaf_storage_state.json` o ejecuta el sync automático.'
        )
    if payload.get('error'):
        raise ValueError(
            'Universo RFAF rechazó la petición (sesión caducada). '
            'Regenera `data/input/rfaf_storage_state.json` o ejecuta el sync automático.'
        )

    def _looks_like_player_row(item) -> bool:
        if not isinstance(item, dict):
            return False
        return bool(str(item.get('nombre') or item.get('name') or item.get('nombre_jugador') or '').strip())

    def _extract_squad(obj):
        if not isinstance(obj, dict):
            return []
        direct_keys = ('plantilla', 'jugadores', 'players', 'roster', 'squad')
        candidates: list[list] = []

        def _score_list(lst) -> tuple[int, int]:
            if not isinstance(lst, list):
                return (0, 0)
            valid = sum(1 for x in lst if _looks_like_player_row(x))
            return (valid, len(lst))

        def _walk(node, depth: int = 0):
            if depth > 6:
                return
            if isinstance(node, list):
                if node and any(_looks_like_player_row(x) for x in node):
                    candidates.append(node)
                for item in node[:80]:
                    _walk(item, depth + 1)
                return
            if isinstance(node, dict):
                for key in direct_keys:
                    value = node.get(key)
                    if isinstance(value, list) and value and any(_looks_like_player_row(x) for x in value):
                        candidates.append(value)
                for value in list(node.values())[:120]:
                    _walk(value, depth + 1)

        _walk(obj, 0)
        if not candidates:
            return []
        candidates.sort(key=lambda lst: _score_list(lst), reverse=True)
        return candidates[0]

    squad = _extract_squad(payload) or []
    if not isinstance(squad, list):
        squad = []
    if squad and not any(isinstance(row, dict) for row in squad):
        squad = []
    if not squad:
        raise ValueError(
            f'Universo RFAF no devolvió plantilla para el equipo {code}. '
            'Prueba a refrescar más tarde o usa La Preferente si está disponible.'
        )

    roster: list[dict] = []
    seen_keys = set()
    for row in squad:
        if not isinstance(row, dict):
            continue
        name = (row.get('nombre') or row.get('name') or row.get('nombre_jugador') or '').strip()
        if not name:
            continue
        code_key = str(row.get('codigo_jugador') or row.get('code') or row.get('id') or '').strip()
        uniq = f'code:{code_key}' if code_key else f'name:{normalize_label(name)}'
        if uniq in seen_keys:
            continue
        seen_keys.add(uniq)
        dorsal = _parse_int_safe(row.get('dorsal') or row.get('dorsal_jugador') or row.get('numero') or row.get('number') or 0)
        roster.append(
            {
                'name': name,
                'position': (row.get('posicion') or row.get('posicion_jugador') or row.get('position') or '').strip(),
                'age': _parse_int_safe(row.get('edad') or row.get('age') or 0),
                'pc': 0,
                'pj': 0,
                'pt': 0,
                'minutes': 0,
                'goals': 0,
                'yellow_cards': 0,
                'red_cards': 0,
                'dorsal': dorsal,
                'code': code_key,
            }
        )

    stats_enabled = str(os.getenv('UNIVERSO_ROSTER_STATS_ENABLED', '1') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    if not stats_enabled or not roster:
        return roster

    def _normalize_key(text: str) -> str:
        return re.sub(r'\s+', ' ', str(text or '').strip().lower())

    def _fetch_player_general_stats(player_id: str) -> dict:
        payload = universo_api_post('player/get-player-general-stats', {'id_player': str(player_id)})
        if not isinstance(payload, dict) or str(payload.get('estado') or '').strip() != '1':
            return {}
        partidos_map = {}
        for entry in payload.get('partidos') or []:
            if isinstance(entry, dict):
                partidos_map[_normalize_key(entry.get('nombre'))] = str(entry.get('valor') or '').strip()
        tarjetas_map = {}
        for entry in payload.get('tarjetas') or []:
            if isinstance(entry, dict):
                tarjetas_map[_normalize_key(entry.get('nombre'))] = str(entry.get('valor') or '').strip()
        return {
            'name': str(payload.get('nombre_jugador') or '').strip(),
            'position': str(payload.get('posicion_jugador') or '').strip(),
            'dorsal': _parse_int_safe(payload.get('dorsal_jugador') or 0),
            'age': _parse_int_safe(payload.get('edad') or 0),
            'pj': _parse_int_safe(partidos_map.get('jugados') or partidos_map.get('partidos jugados') or 0),
            'pt': _parse_int_safe(partidos_map.get('titular') or 0),
            'minutes': _parse_int_safe(payload.get('minutos_totales_jugados') or 0),
            'goals': _parse_int_safe(partidos_map.get('total goles') or partidos_map.get('goles') or 0),
            'yellow_cards': _parse_int_safe(tarjetas_map.get('amarillas') or 0),
            'red_cards': _parse_int_safe(tarjetas_map.get('rojas') or 0),
        }

    max_players = max(0, int(os.getenv('UNIVERSO_ROSTER_STATS_MAX_PLAYERS', '28') or 28))
    max_seconds = max(1.0, float(os.getenv('UNIVERSO_ROSTER_STATS_MAX_SECONDS', '5.5') or 5.5))
    started = timezone.now().timestamp()
    enriched = 0
    for item in roster:
        if max_players and enriched >= max_players:
            break
        if timezone.now().timestamp() - started > max_seconds:
            break
        pid = str(item.get('code') or '').strip()
        if not pid.isdigit():
            continue
        try:
            stats = _fetch_player_general_stats(pid)
        except Exception:
            stats = {}
        if not stats:
            continue
        for key in ('position', 'dorsal', 'age', 'pj', 'pt', 'minutes', 'goals', 'yellow_cards', 'red_cards'):
            if key in stats and stats.get(key) not in (None, ''):
                item[key] = stats.get(key)
        enriched += 1

    return roster
