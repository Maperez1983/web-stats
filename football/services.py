import csv
import re
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from PIL import Image
import pytesseract
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.template.defaultfilters import slugify
from openpyxl import load_workbook
from django.utils import timezone

from football.models import Competition, Group, Season, Team, TeamStanding


USER_AGENT = 'webstats-crm/1.0'
DOWNLOAD_TEXT_PATTERN = re.compile(r'descarg', re.IGNORECASE)
DOWNLOAD_EXTENSIONS = ('.csv', '.xls', '.xlsx', '.png')
PLAYER_ROSTER_PATH = Path(settings.BASE_DIR) / 'data' / 'input' / 'player-roster.html'
MATCH_LISTS_PATH = Path(settings.BASE_DIR) / 'data' / 'excel' / 'FICHA_PARTIDO.xlsx'
PREFERENTE_USER_AGENT = 'webstats-crm/1.0'


def normalize_header(value):
    if value is None:
        return ''
    text = str(value).strip().lower()
    return text.replace(' ', '_')


def ensure_league_structure(competition_name, season_name, group_name):
    competition, _ = Competition.objects.get_or_create(
        name=competition_name,
        defaults={'slug': slugify(competition_name), 'region': 'Andalucía', 'level': 5},
    )
    season, _ = Season.objects.get_or_create(
        competition=competition,
        name=season_name,
        defaults={'is_current': True},
    )
    group_slug = slugify(group_name)
    group, _ = Group.objects.get_or_create(
        season=season,
        slug=group_slug,
        defaults={'name': group_name},
    )
    return competition, season, group


def update_team_standings(rows, source_label, source_url, competition_name='División de Honor Andaluza', season_name='2025/2026', group_name='Grupo 2'):
    _, season, group = ensure_league_structure(competition_name, season_name, group_name)
    updated_slugs = set()
    for idx, row in enumerate(rows, start=1):
        team_name = row.get('team') or row.get('equipo')
        if not team_name:
            continue
        team_slug = slugify(team_name)
        team, _ = Team.objects.get_or_create(
            slug=team_slug,
            defaults={'name': team_name, 'group': group},
        )
        updated_slugs.add(team.slug)
        update_fields = []
        if team.group != group:
            team.group = group
            update_fields.append('group')
        if 'benagalbon' in team.slug.lower():
            if not team.is_primary:
                team.is_primary = True
                update_fields.append('is_primary')
        if update_fields:
            team.save(update_fields=update_fields)

        position_value = _int_or(row.get('position'), default=idx)
        played_value = _int_or(row.get('played') or row.get('pj'))
        wins_value = _int_or(row.get('wins') or row.get('pg'))
        draws_value = _int_or(row.get('draws') or row.get('pe'))
        losses_value = _int_or(row.get('losses') or row.get('pp'))
        goals_for_value = _int_or(row.get('goals_for') or row.get('gf'))
        goals_against_value = _int_or(row.get('goals_against') or row.get('gc'))
        goal_difference_value = _int_or(row.get('goal_difference') or row.get('dg'))
        points_value = _int_or(row.get('points') or row.get('pt') or row.get('pts'))
        standing, _ = TeamStanding.objects.update_or_create(
            season=season,
            group=group,
            team=team,
            defaults={
                'position': position_value,
                'played': played_value,
                'wins': wins_value,
                'draws': draws_value,
                'losses': losses_value,
                'goals_for': goals_for_value,
                'goals_against': goals_against_value,
                'goal_difference': goal_difference_value,
                'points': points_value,
                'last_updated': timezone.now(),
            },
        )
        if standing.points is None:
            wins = standing.wins or 0
            draws = standing.draws or 0
            standing.points = wins * 3 + draws
            standing.save(update_fields=['points'])
        if standing.position is None:
            standing.position = TeamStanding.objects.filter(group=group).count()
            standing.save(update_fields=['position'])
    if updated_slugs:
        TeamStanding.objects.filter(group=group).exclude(team__slug__in=updated_slugs).delete()


def _parse_csv_rows(content):
    text = content.decode('utf-8', errors='ignore')
    reader = csv.DictReader(StringIO(text))
    return [dict(row) for row in reader]


def _parse_excel_rows(content):
    workbook = load_workbook(filename=BytesIO(content), data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) <= 1:
        return []
    header = [normalize_header(cell) for cell in rows[0]]
    parsed = []
    for row in rows[1:]:
        if all(cell is None for cell in row):
            continue
        record = {}
        for idx, value in enumerate(row):
            if idx >= len(header):
                break
            key = header[idx]
            if key:
                record[key] = value
        parsed.append(record)
    return parsed


def _normalize_header_text(value):
    if value is None:
        return ''
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')


def _parse_html_table(soup):
    tables = soup.find_all('table')
    for table in tables:
        header_row = table.find('tr')
        if not header_row:
            continue
        headers = [
            _normalize_header_text(cell.get_text())
            for cell in header_row.find_all(['th', 'td'])
        ]
        if not headers or not any('equipo' in h or 'team' in h for h in headers):
            continue
        rows = []
        for row in table.find_all('tr')[1:]:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            record = {}
            for idx, cell in enumerate(cells):
                if idx >= len(headers):
                    break
                key = headers[idx]
                if not key:
                    continue
                record[key] = cell.get_text(strip=True)
            if record:
                rows.append(record)
        if rows:
            return rows
    return []


def _find_download_link(soup):
    for link in soup.find_all('a', href=True):
        text = link.get_text(' ', strip=True)
        href = link['href']
        if DOWNLOAD_TEXT_PATTERN.search(text) or any(href.lower().endswith(ext) for ext in DOWNLOAD_EXTENSIONS):
            return href
    return None


def _parse_png_rows(content):
    text = pytesseract.image_to_string(Image.open(BytesIO(content)), lang='spa')
    rows = []
    pattern = re.compile(
        r'^\s*(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([+-]?\d+)',
        re.UNICODE,
    )
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            continue
        position, team, points, played, wins, draws, losses, gf, gc, dg = match.groups()
        rows.append(
            {
                'position': position,
                'team': team,
                'points': points,
                'played': played,
                'wins': wins,
                'draws': draws,
                'losses': losses,
                'goals_for': gf,
                'goals_against': gc,
                'goal_difference': dg,
            }
        )
    return rows


def fetch_official_rows(url):
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    download_href = _find_download_link(soup)
    if download_href:
        file_url = urljoin(url, download_href)
        file_response = requests.get(file_url, headers={'User-Agent': USER_AGENT}, timeout=15)
        file_response.raise_for_status()
        ext = urlparse(file_url).path.lower()
        if ext.endswith('.csv'):
            rows = _parse_csv_rows(file_response.content)
            if rows:
                return rows, f'Descarga CSV desde {file_url}'
        elif ext.endswith(('.xls', '.xlsx')):
            rows = _parse_excel_rows(file_response.content)
            if rows:
                return rows, f'Descarga Excel desde {file_url}'
        elif ext.endswith('.png'):
            rows = _parse_png_rows(file_response.content)
            if rows:
                return rows, f'Descarga PNG desde {file_url}'
    # fallback: parse classification table directly if download link missing
    html_rows = _parse_html_table(soup)
    if html_rows:
        return html_rows, 'Clasificación extraída desde la tabla HTML'
    return None, None


def _int_or(value, default=0):
    parsed = _parse_int(value)
    if parsed is None:
        return default
    return parsed


def _parse_int(value):
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def normalize_player_name(value: str) -> str:
    return slugify(value or '')


def _normalize_table_header(value: str) -> str:
    if not value:
        return ''
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def _parse_int_cell(value):
    if value is None:
        return 0
    text = str(value).strip().replace('.', '').replace(',', '')
    if not text or text == '-':
        return 0
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def _extract_name_cell(cell):
    spans = cell.find_all('span')
    if spans:
        text = spans[-1].get_text(' ', strip=True) or spans[0].get_text(' ', strip=True)
        if text:
            return text
    return cell.get_text(' ', strip=True)


def parse_preferente_roster(html: str) -> list[dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id='tablePlantilla')
    if not table:
        for candidate in soup.find_all('table'):
            header = candidate.find('tr')
            if not header:
                continue
            header_text = ' '.join(
                cell.get_text(' ', strip=True).lower() for cell in header.find_all(['th', 'td'])
            )
            if 'jugador' in header_text and 'min' in header_text:
                table = candidate
                break
    if not table:
        return parse_preferente_roster_text(html)
    header_row = table.find('tr')
    if not header_row:
        return []
    headers = [_normalize_table_header(cell.get_text(' ', strip=True)) for cell in header_row.find_all(['th', 'td'])]
    index = {key: idx for idx, key in enumerate(headers) if key}
    roster = []
    for row in table.find_all('tr')[1:]:
        cells = row.find_all('td')
        if len(cells) < 6:
            continue
        name_idx = index.get('jugador', 0)
        pos_idx = index.get('demarcacion', 1)
        name_cell = cells[name_idx] if name_idx < len(cells) else cells[0]
        position_cell = cells[pos_idx] if pos_idx < len(cells) else cells[1]
        name = _extract_name_cell(name_cell)
        if not name:
            continue
        position = position_cell.get_text(' ', strip=True)
        roster.append(
            {
                'name': name,
                'position': position,
                'age': _parse_int_cell(cells[index.get('edad', 0)]) if index.get('edad') is not None else 0,
                'pc': _parse_int_cell(cells[index.get('pc', 0)]) if index.get('pc') is not None else 0,
                'pj': _parse_int_cell(cells[index.get('pj', 0)]) if index.get('pj') is not None else 0,
                'pt': _parse_int_cell(cells[index.get('pt', 0)]) if index.get('pt') is not None else 0,
                'minutes': _parse_int_cell(cells[index.get('min', 0)]) if index.get('min') is not None else 0,
                'goals': _parse_int_cell(cells[index.get('goles', 0)]) if index.get('goles') is not None else 0,
                'yellow_cards': _parse_int_cell(cells[index.get('ta', 0)]) if index.get('ta') is not None else 0,
                'red_cards': _parse_int_cell(cells[index.get('tr', 0)]) if index.get('tr') is not None else 0,
            }
        )
    return roster


def parse_preferente_roster_text(raw: str) -> list[dict]:
    if not raw:
        return []
    lines = [line.strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    status_markers = (
        'Renovado',
        'Nuevo Fichaje',
        'Jugador',
        'Cuerpo Técnico',
        'COMPETICIONES',
        'Ex-Jugadores',
        'Total de Jugadores',
    )
    position_keywords = (
        'Portero',
        'Lateral',
        'Central',
        'Medio',
        'Interior',
        'Media',
        'Extremo',
        'Delantero',
        'Pivote',
    )
    roster = []
    last_name = ''
    for line in lines:
        if any(marker in line for marker in status_markers):
            continue
        if line.isdigit():
            continue
        tokens = line.split()
        if not tokens:
            continue
        has_position = any(keyword in line for keyword in position_keywords)
        has_numbers = any(token.replace('(', '').replace(')', '').isdigit() for token in tokens)
        if has_position and has_numbers:
            position_parts = []
            stat_tokens = []
            for token in tokens:
                cleaned = token.replace('(', '').replace(')', '')
                if cleaned.replace('-', '').isdigit() or cleaned == '-':
                    stat_tokens.append(cleaned)
                else:
                    position_parts.append(token)
            position = ' '.join(position_parts).strip()
            numbers = [int(t) for t in stat_tokens if t.isdigit()]
            while len(numbers) < 8:
                numbers.append(0)
            age, pc, pj, pt, minutes, goals, yellow, red = numbers[:8]
            if last_name:
                roster.append(
                    {
                        'name': last_name,
                        'position': position,
                        'age': age,
                        'pc': pc,
                        'pj': pj,
                        'pt': pt,
                        'minutes': minutes,
                        'goals': goals,
                        'yellow_cards': yellow,
                        'red_cards': red,
                    }
                )
            continue
        last_name = line
    return roster


def fetch_preferente_team_roster(team_url: str) -> list[dict]:
    if not team_url:
        return []
    response = requests.get(team_url, headers={'User-Agent': PREFERENTE_USER_AGENT}, timeout=20)
    response.raise_for_status()
    return parse_preferente_roster(response.text)


def compute_probable_eleven(players: list[dict]) -> list[dict]:
    if not players:
        return []
    eligible = [p for p in players if p.get('minutes', 0) > 0]
    eligible.sort(key=lambda p: (p.get('minutes', 0), p.get('pt', 0), p.get('pj', 0)), reverse=True)
    gks = [p for p in eligible if 'portero' in (p.get('position') or '').lower()]
    lineup = []
    if gks:
        lineup.append(gks[0])
    for player in eligible:
        if player in lineup:
            continue
        lineup.append(player)
        if len(lineup) >= 11:
            break
    return lineup[:11]


def build_rival_insights(players: list[dict]) -> dict:
    if not players:
        return {'top_scorers': [], 'most_minutes': [], 'most_cards': []}
    top_scorers = sorted(players, key=lambda p: (p.get('goals', 0), p.get('minutes', 0)), reverse=True)[:3]
    most_minutes = sorted(players, key=lambda p: p.get('minutes', 0), reverse=True)[:3]
    most_cards = sorted(
        players,
        key=lambda p: (p.get('red_cards', 0) * 2 + p.get('yellow_cards', 0)),
        reverse=True,
    )[:3]
    return {
        'top_scorers': top_scorers,
        'most_minutes': most_minutes,
        'most_cards': most_cards,
    }


def load_player_roster_stats() -> dict:
    if not PLAYER_ROSTER_PATH.exists():
        return {}
    try:
        html = PLAYER_ROSTER_PATH.read_text(encoding='utf-8')
    except Exception:
        try:
            html = PLAYER_ROSTER_PATH.read_text(encoding='latin-1', errors='ignore')
        except Exception:
            return {}
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id='tablePlantilla')
    if not table:
        return {}
    roster = {}
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 11:
            continue
        name_cell = cells[2]
        spans = name_cell.find_all('span')
        if not spans:
            continue
        full_name = spans[-1].get_text(' ', strip=True) or spans[0].get_text(' ', strip=True)
        if not full_name:
            continue
        position = cells[3].get_text(' ', strip=True)
        normalized_name = normalize_player_name(full_name)
        roster[normalized_name] = {
            'name': full_name,
            'position': position,
            'age': _parse_int(cells[5].get_text(' ', strip=True)) or 0,
            'pc': _parse_int(cells[6].get_text(' ', strip=True)) or 0,
            'pj': _parse_int(cells[7].get_text(' ', strip=True)) or 0,
            'pt': _parse_int(cells[8].get_text(' ', strip=True)) or 0,
            'minutes': _parse_int(cells[9].get_text(' ', strip=True)) or 0,
            'goals': _parse_int(cells[10].get_text(' ', strip=True)) or 0,
            'yellow_cards': _parse_int(cells[11].get_text(' ', strip=True)) or 0,
            'red_cards': _parse_int(cells[12].get_text(' ', strip=True)) or 0,
            'assists': 0,
        }
    return roster


_ROSTER_CACHE = None


def get_roster_stats_cache() -> dict:
    global _ROSTER_CACHE
    if _ROSTER_CACHE is None:
        _ROSTER_CACHE = load_player_roster_stats()
    return _ROSTER_CACHE


ALIAS_MAP = {
    'antonio': 'antonio-gamez-paniagua',
    'andrew': 'andrew-brayce-gonzales-ticona',
    'andrews': 'andrew-brayce-gonzales-ticona',
    'andrew-brayce-gonzales-ticona': 'andrew-brayce-gonzales-ticona',
    'manu': 'manuel-torres-palenzuela',
    'lolo': 'manuel-fernandez-canete',
    'jaime': 'javier-gutierrez-palma',
    'javi': 'javier-gutierrez-palma',
    'martinez': 'antonio-martinez-campens',
    'nico': 'nicolas-villalba-alcaide',
    'nicolas': 'nicolas-villalba-alcaide',
    'nacho': 'ignacio-dorado-morales',
    'ivan': 'ivan-fernandez-reina',
    'yaco': 'yaco-uriel-campoamor',
    'acosta': 'jose-garcia-acosta',
    'francis': 'francisco-javier-ruiz-perez',
    'juanmi': 'juan-miguel-anaya-bustamante',
    'victor': 'victor-ruiz-postigo',
    'antonio-ruiz': 'antonio-vilches',
}


def canonical_roster_key(player_name: str) -> str:
    normalized = normalize_player_name(player_name)
    return ALIAS_MAP.get(normalized, normalized)


def find_roster_entry(player_name: str, roster: dict) -> Optional[dict]:
    key = canonical_roster_key(player_name)
    if key:
        entry = roster.get(key)
        if entry:
            return entry
    target = player_name.lower().strip()
    if not target:
        return None
    for entry in roster.values():
        entry_name = entry['name'].lower()
        if target in entry_name or entry_name in target:
            return entry
    return None


_MATCH_LIST_CACHE = None
_MATCH_RESULT_CACHE = None


def _read_match_list_sheet():
    global _MATCH_LIST_CACHE, _MATCH_RESULT_CACHE
    if _MATCH_LIST_CACHE is not None and _MATCH_RESULT_CACHE is not None:
        return _MATCH_LIST_CACHE, _MATCH_RESULT_CACHE
    actions = []
    results = []
    seen_actions = set()
    seen_results = set()
    if not MATCH_LISTS_PATH.exists():
        _MATCH_LIST_CACHE = actions
        _MATCH_RESULT_CACHE = results
        return actions, results
    try:
        workbook = load_workbook(filename=MATCH_LISTS_PATH, read_only=True, data_only=True)
        if 'LISTAS' in workbook.sheetnames:
            sheet = workbook['LISTAS']
            for row in sheet.iter_rows(values_only=True):
                if not row:
                    continue
                action_label = (row[0] or '').strip()
                result_label = (row[1] or '').strip()
                if action_label:
                    key = action_label.upper()
                    if key not in seen_actions:
                        seen_actions.add(key)
                        actions.append(action_label)
                if result_label:
                    key = result_label.upper()
                    if key not in seen_results:
                        seen_results.add(key)
                        results.append(result_label)
    except Exception:
        pass
    _MATCH_LIST_CACHE = actions
    _MATCH_RESULT_CACHE = results
    return actions, results


DEFAULT_QUICK_ACTIONS = ['Disparo', 'Pase clave', 'Robo', 'Falta', 'Cambio', 'Duelo aéreo', 'Regate']

def load_match_actions():
    actions, _ = _read_match_list_sheet()
    if not actions:
        return DEFAULT_QUICK_ACTIONS.copy()
    ordered = []
    seen = set()
    for action in actions:
        normalized = action.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(action.strip())
    for extra in DEFAULT_QUICK_ACTIONS:
        normalized = extra.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(extra)
    return ordered


def load_match_results():
    _, results = _read_match_list_sheet()
    return results or ['Ganado', 'Perdido', 'Neutral']
