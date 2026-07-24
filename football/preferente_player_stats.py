"""Scraping de estadísticas por jugador y temporada desde La Preferente.

La página de equipo por temporada (``E{codigo}T{aaaaaaaa}/slug``) trae la
plantilla con columnas: Demarcación, Edad, PC, PJ, PT, Min, Goles, TA, TR.
Es server-side (charset iso-8859-1) → parseable sin navegador. Se emparejan
los jugadores por nombre con las fichas locales y se vuelca en
``ExternalSeasonStat`` (no pisa las stats propias)."""
from __future__ import annotations

import logging
import re
import unicodedata

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DEMARCACIONES = (
    "portero", "central", "lateral", "defensa", "medio", "pivote", "media punta",
    "mediapunta", "extremo", "delantero", "centrocampista", "interior", "carrilero",
)
_CLUB_MARKERS = (" c.f", " cf", " c.d", " cd ", " u.d", " ud ", " f.c", " fc", "atlético", "atletico", "club ")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.strip().lower())


def _int(x) -> int:
    m = re.search(r"-?\d+", str(x or ""))
    return int(m.group()) if m else 0


def parse_preferente_squad(html: str) -> list:
    """Devuelve lista de dicts por jugador de la tabla de plantilla."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
        if len(cells) < 11:
            continue
        name = (cells[2] or "").strip()
        pos = (cells[3] or "").strip()
        nlow = _norm(name)
        if len(nlow) < 3 or not re.search(r"[a-z]", nlow):
            continue
        if any(mk in " " + nlow + " " for mk in _CLUB_MARKERS):
            continue  # fila de clasificación (nombre de equipo)
        plow = _norm(pos)
        if not (plow == "" or any(d in plow for d in _DEMARCACIONES)):
            continue  # pos numérica => clasificación
        tail = cells[-8:]
        nums = [c for c in tail if re.fullmatch(r"\(?-?\d+\)?", c or "")]
        if len(nums) < 6:
            continue
        goles_raw = cells[-3] or ""
        conceded = _int(goles_raw) if goles_raw.strip().startswith("(") else None
        goals = 0 if conceded is not None else _int(goles_raw)
        rows.append({
            "external_name": name,
            "position": pos,
            "matches": _int(cells[-6]),      # PJ
            "starts": _int(cells[-5]),       # PT (titular)
            "minutes": _int(cells[-4]),      # Min
            "goals": goals,
            "goals_conceded": conceded,
            "yellow_cards": _int(cells[-2]),
            "red_cards": _int(cells[-1]),
        })
    # dedupe por nombre
    seen, out = set(), []
    for r in rows:
        k = _norm(r["external_name"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def team_code_from_url(url: str) -> str:
    """Extrae 'E147' de una URL de equipo de La Preferente."""
    m = re.search(r"/(E\d+)", str(url or ""))
    return m.group(1) if m else ""


def season_team_url(team_code: str, season_label: str, slug: str = "equipo") -> str:
    yy = season_label.replace("/", "").strip()
    return f"https://www.lapreferente.com/{team_code}T{yy}/{slug}"


def _match_player(external_name: str, players: list):
    """Empareja un nombre externo con una ficha Player por nombre normalizado."""
    ext = set(_norm(external_name).split())
    best, best_score = None, 0
    for p in players:
        for cand in (getattr(p, "full_name", ""), getattr(p, "name", ""), getattr(p, "nickname", "")):
            toks = set(_norm(cand).split())
            if not toks:
                continue
            inter = len(toks & ext)
            if inter >= 2 and inter > best_score:  # al menos 2 tokens (nombre+apellido)
                best, best_score = p, inter
    return best
