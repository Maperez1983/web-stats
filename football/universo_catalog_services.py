import json
import re

from django.utils import timezone
from django.utils.dateparse import parse_date

from .team_media_services import UNIVERSO_CAPTURE_PATH


def load_universo_capture():
    if not UNIVERSO_CAPTURE_PATH.exists():
        return {}
    try:
        payload = json.loads(UNIVERSO_CAPTURE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_capture_form_payload(raw_payload):
    parsed = {}
    raw_text = str(raw_payload or '')
    if not raw_text:
        return parsed
    pattern = (
        r'name="([^"]+)"\r\n\r\n'
        r'(.*?)(?=\r\n--|\r\nContent-Disposition: form-data; name=|$)'
    )
    for match in re.finditer(pattern, raw_text, re.S):
        parsed[str(match.group(1) or '').strip()] = str(match.group(2) or '').strip()
    return parsed


def derive_season_label_from_dates(start_value, end_value):
    start_date = parse_date(str(start_value or '').strip())
    end_date = parse_date(str(end_value or '').strip())
    if start_date and end_date:
        return f'{start_date.year}/{end_date.year}'
    if start_date:
        return f'{start_date.year}/{start_date.year + 1}'
    if end_date:
        return f'{end_date.year - 1}/{end_date.year}'
    today = timezone.localdate()
    if today.month >= 7:
        return f'{today.year}/{today.year + 1}'
    return f'{today.year - 1}/{today.year}'


def extract_region_from_competition_name(name):
    text = str(name or '').strip()
    match = re.search(r'\(([^)]+)\)\s*$', text)
    return str(match.group(1) or '').strip() if match else ''


def build_universo_competition_catalog(payload=None):
    payload = load_universo_capture() if payload is None else payload
    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {
            'competitions': {},
            'groups': {},
            'classifications': {},
        }
    competitions = {}
    groups = {}
    classifications = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url') or '').strip()
        data = item.get('json')
        if not isinstance(data, dict):
            continue
        post_data = parse_capture_form_payload(item.get('request_post_data'))
        if 'competition/get-competitions' in url:
            for row in data.get('competiciones') or []:
                if not isinstance(row, dict):
                    continue
                code = str(row.get('codigo') or '').strip()
                if not code:
                    continue
                competitions[code] = {
                    'code': code,
                    'name': str(row.get('nombre') or '').strip(),
                    'category_name': str(row.get('NombreCategoria') or '').strip(),
                    'game_type': str(row.get('TipoJuego') or '').strip(),
                    'season_id': str(post_data.get('id_season') or '').strip(),
                    'start_date': str(row.get('FechaInicio') or '').strip(),
                    'end_date': str(row.get('FechaFin') or '').strip(),
                    'season_name': derive_season_label_from_dates(
                        row.get('FechaInicio'),
                        row.get('FechaFin'),
                    ),
                    'region': extract_region_from_competition_name(row.get('nombre')),
                }
        elif 'competition/get-groups' in url:
            competition_code = str(post_data.get('id_competition') or '').strip()
            if not competition_code:
                continue
            for row in data.get('grupos') or []:
                if not isinstance(row, dict):
                    continue
                group_code = str(row.get('codigo') or '').strip()
                if not group_code:
                    continue
                groups[(competition_code, group_code)] = {
                    'competition_code': competition_code,
                    'group_code': group_code,
                    'group_name': str(row.get('nombre') or '').strip(),
                    'total_rounds': str(row.get('total_jornadas') or '').strip(),
                    'total_teams': str(row.get('total_equipos') or '').strip(),
                }
        elif 'competition/get-classification' in url:
            competition_code = str(data.get('codigo_competicion') or '').strip()
            group_code = str(data.get('codigo_grupo') or '').strip()
            if not competition_code or not group_code:
                continue
            classifications[(competition_code, group_code)] = {
                'competition_code': competition_code,
                'competition_name': str(data.get('competicion') or '').strip(),
                'group_code': group_code,
                'group_name': str(data.get('grupo') or '').strip(),
                'round': str(data.get('jornada') or '').strip(),
                'round_date': str(data.get('fecha_jornada') or '').strip(),
                'rows': [row for row in (data.get('clasificacion') or []) if isinstance(row, dict)],
            }
    return {
        'competitions': competitions,
        'groups': groups,
        'classifications': classifications,
    }
