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

from bs4 import BeautifulSoup

from .competition_season_services import normalize_season_name

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
    return rows, parse_preferente_competition_meta(html)
