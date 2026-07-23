"""
Clasificación en vivo de La Preferente para el contexto competitivo del club.

Complementa a Universo RFAF: hasta ahora el sync de competición solo traía clasificación/próximo
rival para el provider Universo; La Preferente se usaba solo para plantillas. Aquí parseamos la
tabla de clasificación de la ficha de equipo de lapreferente.com y la normalizamos al mismo
formato que `serialize_universo_standings`, para que el resto del pipeline (snapshot, portada del
entrenador) la consuma sin cambios.

El spike `preferente_standings_probe` confirmó que el servidor puede leer estas páginas (HTTP 200,
sin muro anti-bot en la ficha de equipo). Reutilizamos `_fetch_preferente_response`, que ya mantiene
sesión/cookies para minimizar 403.
"""

from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from .competition_season_services import normalize_season_name

# Endpoint jaxon (mismo que usa el JS de la web) para el panel de partidos. Se puede llamar
# servidor->web con `requests` (verificado): en pretemporada devuelve un error PHP porque no hay
# jornada, y cuando el calendario esté sorteado devolverá el HTML del panel de resultados.
_JAXON_URL = 'https://www.lapreferente.com/jaxon/ajax.php'
_JAXON_VERSION = '4.0.2'

# href de equipo en la clasificación: E<team>C<competition>-<n>/slug
_TEAM_COMP_HREF_RE = re.compile(r'\bE(\d+)C(\d+)\b', re.IGNORECASE)
# id de equipo en la URL de la ficha: /E147/cd-benagalbon
_URL_TEAM_ID_RE = re.compile(r'/E(\d+)\b', re.IGNORECASE)

# La tabla de clasificación de la ficha de equipo tiene id fijo `tableClasif` (class lpfTable01).
# OJO: hay una tabla duplicada (versión móvil) sin id que concatena todas las filas; NO usarla.
_STANDINGS_TABLE_ID = 'tableClasif'

# Marcadores de muro anti-bot; si aparecen, no hay clasificación fiable que devolver.
_BLOCK_MARKERS = (
    'just a moment',
    'attention required',
    'cf-challenge',
    'captcha',
    '__cf_chl',
)

# Orden de columnas en tableClasif (celdas directas por fila):
#   0=posición  1=escudo(vacío)  2=equipo  3=PT(puntos)  4=PJ  5=PG  6=PE  7=PP  8=GF  9=GC  10=DG  11=S(racha)
_COL = {
    'position': 0,
    'team': 2,
    'points': 3,
    'played': 4,
    'wins': 5,
    'draws': 6,
    'losses': 7,
    'goals_for': 8,
    'goals_against': 9,
    'goal_difference': 10,
}

# href de equipo: E<code>C<competition>-<n>/slug  ->  capturamos E<code> y C<competition>.
_TEAM_HREF_RE = re.compile(r'\bE(\d+)C(\d+)\b', re.IGNORECASE)


def _to_int(value):
    text = str(value or '').strip().replace('\xa0', '')
    if not text:
        return None
    match = re.search(r'-?\d+', text)
    return int(match.group(0)) if match else None


def _row_cells(row):
    # recursive=False: la web anida tablas dentro de celdas; sin esto salen cientos de celdas basura.
    return [cell.get_text(' ', strip=True) for cell in row.find_all(['td', 'th'], recursive=False)]


def parse_preferente_standings(html):
    """
    Devuelve la lista de filas de clasificación normalizadas (mismo formato que Universo):
    rank, team, full_name, team_code, played, wins, draws, losses, goals_for, goals_against,
    goal_difference, points. Lista vacía si no hay tabla o el HTML viene bloqueado.
    """
    if not html:
        return []
    lowered = html.lower()
    if any(marker in lowered for marker in _BLOCK_MARKERS):
        return []
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id=_STANDINGS_TABLE_ID)
    if table is None:
        return []

    rows = []
    for tr in table.find_all('tr'):
        cells = _row_cells(tr)
        if len(cells) <= _COL['goal_difference']:
            continue
        name = str(cells[_COL['team']] or '').strip()
        if not name or name.lower() == 'equipo':  # cabecera
            continue
        position = _to_int(cells[_COL['position']])
        if position is None:
            continue
        team_code = ''
        link = tr.find('a', href=True)
        if link:
            match = _TEAM_HREF_RE.search(link['href'])
            if match:
                team_code = f'E{match.group(1)}'
        goals_for = _to_int(cells[_COL['goals_for']])
        goals_against = _to_int(cells[_COL['goals_against']])
        goal_difference = _to_int(cells[_COL['goal_difference']])
        if goal_difference is None and goals_for is not None and goals_against is not None:
            goal_difference = goals_for - goals_against
        wins = _to_int(cells[_COL['wins']])
        draws = _to_int(cells[_COL['draws']])
        points = _to_int(cells[_COL['points']])
        if points is None and wins is not None and draws is not None:
            points = wins * 3 + draws
        rows.append(
            {
                'rank': position,
                'team': name.upper(),
                'full_name': name,
                'team_code': team_code,
                'crest_url': '',
                'played': _to_int(cells[_COL['played']]) or 0,
                'wins': wins or 0,
                'draws': draws or 0,
                'losses': _to_int(cells[_COL['losses']]) or 0,
                'goals_for': goals_for or 0,
                'goals_against': goals_against or 0,
                'goal_difference': goal_difference if goal_difference is not None else 0,
                'points': points or 0,
            }
        )
    rows.sort(key=lambda item: (item['rank'] <= 0, item['rank']))
    return rows


def parse_preferente_competition_meta(html):
    """
    Extrae, best-effort, la temporada visible en la ficha para etiquetar los datos.

    Nota: la ficha de equipo mezcla mucho texto de menús/rankings, así que NO intentamos derivar el
    nombre de competición/grupo desde aquí (sale poco fiable); para eso el wire usa el grupo ya
    vinculado al equipo. La temporada (`Temporada: AAAA/AAAA`) sí es un dato limpio y localizado.
    """
    meta = {}
    if not html:
        return meta
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    season = re.search(r'Temporada:\s*(\d{4}\s*/\s*\d{4})', text)
    if season:
        meta['season_name'] = normalize_season_name(season.group(1)) or season.group(1).replace(' ', '')
    return meta


def fetch_preferente_standings(url):
    """
    Descarga y parsea la clasificación desde una URL de La Preferente (ficha de equipo o
    clasificación). Devuelve (rows, meta). ([], {}) si viene bloqueado o falla la red.
    """
    url = str(url or '').strip()
    if not url:
        return [], {}
    # Import perezoso para no acoplar este módulo al de services (evita ciclos en import).
    from .services import _fetch_preferente_response

    try:
        response = _fetch_preferente_response(url)
    except Exception:
        return [], {}
    if getattr(response, 'status_code', 0) != 200:
        return [], {}
    html = response.text or ''
    rows = parse_preferente_standings(html)
    if not rows:
        return [], {}
    meta = parse_preferente_competition_meta(html)
    competition_code = extract_preferente_competition_code(html)
    if competition_code:
        meta['competition_code'] = competition_code
    return rows, meta


def extract_preferente_competition_code(html):
    """El código de competición (C#####) compartido por los enlaces de equipo de la clasificación."""
    if not html:
        return ''
    codes = {}
    for match in _TEAM_COMP_HREF_RE.finditer(html):
        code = match.group(2)
        codes[code] = codes.get(code, 0) + 1
    if not codes:
        return ''
    return max(codes, key=codes.get)


def _preferente_team_id_from_url(url):
    match = _URL_TEAM_ID_RE.search(str(url or ''))
    return match.group(1) if match else ''


def _looks_like_php_error(text):
    lowered = str(text or '').lower()
    return 'fatal error' in lowered or 'uncaught' in lowered or '<b>warning</b>' in lowered


def parse_preferente_next_match(panel_html, *, team_id=''):
    """
    Extrae el próximo partido del panel de resultados de La Preferente.

    NOTA DE VALIDACIÓN: en pretemporada 2026 el calendario no está sorteado, así que no hay HTML de
    panel real contra el que validar el desglose fila a fila. Este parser es best-effort y degrada a
    {} si no encuentra un partido con fecha futura y rival claros; nunca inventa. Cuando el calendario
    exista, hay que revisar el mapeo de celdas con un panel poblado (el endpoint y el flujo ya están
    verificados de punta a punta).
    """
    if not panel_html or _looks_like_php_error(panel_html):
        return {}
    soup = BeautifulSoup(panel_html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if not text:
        return {}
    # Estructura esperada (a confirmar con datos reales): filas con equipos enlazados y una fecha.
    date_match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
    team_links = [a.get_text(' ', strip=True) for a in soup.find_all('a') if a.get_text(strip=True)]
    if not date_match or len(team_links) < 2:
        return {}
    from datetime import datetime

    try:
        match_date = datetime.strptime(date_match.group(1), '%d/%m/%Y').date().isoformat()
    except ValueError:
        return {}
    home_name, away_name = team_links[0], team_links[1]
    opponent = away_name if home_name else away_name
    return {
        'round': '',
        'date': match_date,
        'time': '',
        'location': '',
        'opponent': {'name': opponent, 'full_name': opponent, 'crest_url': ''},
        'home': True,
        'status': 'next',
        'source': 'lapreferente',
    }


def fetch_preferente_next_match(preferente_url, *, competition_code=''):
    """
    Próximo partido desde La Preferente vía el endpoint jaxon `Ajax.Partidos.recargaPanelResultados`.

    Devuelve un payload de próximo partido normalizado, o {} si el calendario aún no está sorteado
    (La Preferente responde con error PHP en ese caso) o si no se puede resolver. Diseñado para
    correr servidor->web sin navegador (verificado).
    """
    url = str(preferente_url or '').strip()
    team_id = _preferente_team_id_from_url(url)
    if not team_id:
        return {}
    from .services import _fetch_preferente_response, _get_preferente_session, _preferente_headers

    if not competition_code:
        try:
            page = _fetch_preferente_response(url)
            competition_code = extract_preferente_competition_code(page.text or '')
        except Exception:
            competition_code = ''
    if not competition_code:
        return {}

    session = _get_preferente_session()
    headers = _preferente_headers(url)
    headers['X-Requested-With'] = 'XMLHttpRequest'
    body = {
        'jxnr': str(int(time.time() * 1000)),
        'jxnv': _JAXON_VERSION,
        'jxncls': 'Ajax.Partidos',
        'jxnmthd': 'recargaPanelResultados',
        # Codificación de args jaxon: N<numero>. Firma: (competición, equipo, panel=1).
        'jxnargs[]': [f'N{competition_code}', f'N{team_id}', 'N1'],
    }
    try:
        response = session.post(_JAXON_URL, data=body, headers=headers, timeout=20)
    except Exception:
        return {}
    if getattr(response, 'status_code', 0) != 200:
        return {}
    return parse_preferente_next_match(response.text or '', team_id=team_id)
