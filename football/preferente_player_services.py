"""Parseo de la ficha de un jugador de La Preferente (texto pegado) para crear un ojeado.

La Preferente bloquea el acceso desde el servidor (403), así que no podemos descargar la
página. En su lugar, el usuario copia el texto de la ficha del jugador (Cmd+A, Cmd+C) y lo
pega; aquí lo convertimos en datos estructurados: cabecera (nombre, posición, club, fecha de
nacimiento…) y el historial por temporada (equipo, división, PJ, PT, goles, tarjetas).
"""

import re

_SEASON_RE = re.compile(r"^\d{4}\s*/\s*\d{4}$")
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_NUMERIC_RE = re.compile(r"^-?[\d.]+$")


def _to_int(value):
    text = str(value or "").strip().replace(".", "").replace("\xa0", "")
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def _label_value(lines, label_regex):
    pattern = re.compile(rf"^{label_regex}\s*:\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""


def parse_preferente_player(text):
    """Devuelve un dict con los datos del jugador y su historial por temporada.

    {
      'name', 'current_team', 'position', 'specific_position', 'birth_place',
      'birth_date' (ISO YYYY-MM-DD o ''), 'origin_team',
      'seasons': [ {season, team, division, matches_completed, matches_starter,
                    goals, yellow_cards, red_cards}, ... ]
    }
    """
    raw_lines = str(text or "").splitlines()
    lines = [ln.strip() for ln in raw_lines]

    # --- Cabecera ---
    position = ""
    specific_position = ""
    for line in lines:
        m = re.match(r"^POSICI[ÓO]N\s+ESPEC[ÍI]FICA\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            specific_position = m.group(1).strip()
            continue
        m = re.match(r"^POSICI[ÓO]N\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            position = m.group(1).strip()

    current_team = _label_value(lines, r"CLUB AL QUE PERTENECE")
    birth_place = _label_value(lines, r"LUGAR DE NACIMIENTO")
    origin_team = _label_value(lines, r"EQUIPO DE PROCEDENCIA")
    birth_raw = _label_value(lines, r"FECHA DE NACIMIENTO")
    birth_date = ""
    dm = _DATE_RE.search(birth_raw)
    if dm:
        birth_date = f"{dm.group(3)}-{int(dm.group(2)):02d}-{int(dm.group(1)):02d}"

    # Nombre: la última línea "de texto" justo antes de "CLUB AL QUE PERTENECE".
    name = ""
    for i, line in enumerate(lines):
        if re.match(r"^CLUB AL QUE PERTENECE", line, re.IGNORECASE):
            for j in range(i - 1, -1, -1):
                cand = lines[j]
                if cand and len(cand) >= 4 and ":" not in cand and cand != cand.upper():
                    name = cand
                    break
            break

    # --- Historial por temporada ---
    seasons = []
    current_season = ""
    for i, raw in enumerate(raw_lines):
        s = raw.strip()
        if _SEASON_RE.match(s):
            current_season = s.replace(" ", "")
            continue
        if "\t" not in raw:
            continue
        parts = raw.split("\t")
        # Índice del rol: primer token no vacío y no numérico (p.ej. "Extremo Derecho").
        role_idx = None
        for idx, tok in enumerate(parts):
            t = tok.strip()
            if t and not _NUMERIC_RE.match(t):
                role_idx = idx
                break
        if role_idx is None:
            continue
        tail = [p.strip() for p in parts[role_idx + 1:]]
        # Deben venir al menos las columnas PC..P (10). Si no, no es una fila de stats.
        numericish = [p for p in tail if p == "" or _NUMERIC_RE.match(p)]
        if len(numericish) < 10:
            continue
        # Posicional: PC, PJ, PT, MIN, GOL, TA, TR, G, E, P
        vals = (numericish + [""] * 10)[:10]
        team, division = "", ""
        prev = [lines[k] for k in range(i - 1, max(-1, i - 8), -1) if lines[k]]
        if len(prev) >= 1:
            division = prev[0]
        if len(prev) >= 2:
            team = prev[1]
        seasons.append(
            {
                "season": current_season,
                "team": team[:160],
                "division": division[:120],
                "matches_completed": _to_int(vals[1]),  # PJ
                "matches_starter": _to_int(vals[2]),     # PT
                "goals": _to_int(vals[4]),               # GOL
                "yellow_cards": _to_int(vals[5]),        # TA
                "red_cards": _to_int(vals[6]),           # TR
            }
        )

    return {
        "name": name,
        "current_team": current_team,
        "position": position,
        "specific_position": specific_position,
        "birth_place": birth_place,
        "birth_date": birth_date,
        "origin_team": origin_team,
        "seasons": seasons,
    }
