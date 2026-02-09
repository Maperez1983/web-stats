import csv
import json
import re
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

URL = (
    "https://www.rfaf.es/pnfg/NPcd/NFG_VisClasificacion?cod_primaria=1000120&"
    "codgrupo=45030656&codcompeticion=45030612"
)
SCHEDULE_TEMPLATE = (
    "https://www.rfaf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120&"
    "CodTemporada=21&CodGrupo=45030656&CodCompeticion=45030612&CodJornada={jornada}"
)
BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT = BASE_DIR / "data" / "input" / "rfaf-standings.csv"
NEXT_MATCH_FILE = BASE_DIR / "data" / "input" / "rfaf-next-match.json"
FALLBACK_HTML = Path("/Volumes/Mac Satecchi/Mac/rfaf- visualización de Clasificación.html")
HEADERS = [
    "position",
    "team",
    "played",
    "wins",
    "draws",
    "losses",
    "goals_for",
    "goals_against",
    "goal_difference",
    "points",
]

USER_AGENT = "webstats-crm/1.0"


def _parse_int(value: str) -> int:
    if not value:
        return 0
    cleaned = re.sub(r"[^0-9+-]", "", value)
    if not cleaned:
        return 0
    try:
        return int(cleaned)
    except ValueError:
        return 0


def _team_text(cell) -> str:
    anchor = cell.find("a")
    if anchor and anchor.text.strip():
        return anchor.get_text(" ", strip=True)
    return cell.get_text(" ", strip=True)


def normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", value)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return normalized.lower().strip()


def fetch_html() -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": (
            "https://www.rfaf.es/pnfg/NPcd/NFG_VisGrupos_Vis?cod_primaria=1000123&codgrupo=45030656"
        ),
    }
    try:
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException:
        if FALLBACK_HTML.exists():
            return FALLBACK_HTML.read_text(encoding="utf-8")
        raise


def parse_table() -> (List[dict], str):
    html = fetch_html()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#CL_Detalle table.table.table-striped")
    if not table:
        table = soup.select_one("#CL_Detalle table")
    if not table:
        table = soup.select_one("#CL_Resumen table.table.table-striped")
    if not table:
        Path("/tmp/rfaf_page.html").write_text(html, encoding="utf-8")
        raise SystemExit(
            "No se encontró la tabla en la página de la federación. "
            "He guardado el HTML descargado en /tmp/rfaf_page.html para que puedas inspeccionarlo."
        )
    records: List[dict] = []
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 14:
            continue
        position_text = cells[1].get_text(strip=True)
        if not position_text or not re.search(r"\d", position_text):
            continue
        team_name = _team_text(cells[2])
        cleaned_team = normalize_text(team_name)
        if not cleaned_team or cleaned_team in {"pts", "pt"}:
            continue
        points_text = cells[3].get_text(strip=True)
        home_j = _parse_int(cells[4].get_text(strip=True))
        home_w = _parse_int(cells[5].get_text(strip=True))
        home_d = _parse_int(cells[6].get_text(strip=True))
        home_l = _parse_int(cells[7].get_text(strip=True))
        away_j = _parse_int(cells[8].get_text(strip=True))
        away_w = _parse_int(cells[9].get_text(strip=True))
        away_d = _parse_int(cells[10].get_text(strip=True))
        away_l = _parse_int(cells[11].get_text(strip=True))
        goals_for = _parse_int(cells[12].get_text(strip=True))
        goals_against = _parse_int(cells[13].get_text(strip=True))
        total_matches = home_j + away_j
        total_wins = home_w + away_w
        total_draws = home_d + away_d
        total_losses = home_l + away_l
        goal_difference = goals_for - goals_against
        record = {
            "position": position_text.strip(),
            "team": team_name,
            "played": str(total_matches),
            "wins": str(total_wins),
            "draws": str(total_draws),
            "losses": str(total_losses),
            "goals_for": str(goals_for),
            "goals_against": str(goals_against),
            "goal_difference": str(goal_difference),
            "points": points_text.strip(),
        }
        records.append(record)
    if not records:
        Path("/tmp/rfaf_page.html").write_text(html, encoding="utf-8")
        raise SystemExit("No se pudieron extraer filas válidas de la tabla.")
    return records, html


def extract_next_match_from_classification(html: str) -> Optional[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("h3")
    for heading in blocks:
        text = heading.get_text(strip=True)
        round_match = re.search(r"Jornada\s*(\d+)", text, re.IGNORECASE)
        date_match = re.search(r"\((\d{2}-\d{2}-\d{4})\)", text)
        round_number = round_match.group(1) if round_match else None
        date_iso = None
        if date_match:
            try:
                date_iso = datetime.strptime(date_match.group(1), "%d-%m-%Y").date().isoformat()
            except ValueError:
                date_iso = None
        table = heading.find_next("table")
        if not table:
            continue
        latest_payload = None
        for row in table.select("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            home_name = cells[0].get_text(" ", strip=True)
            score_text = cells[1].get_text(" ", strip=True)
            away_name = cells[2].get_text(" ", strip=True)
            home_norm = normalize_text(home_name)
            away_norm = normalize_text(away_name)
            total_score_digits = re.search(r"\d", score_text)
            is_future = not bool(total_score_digits)
            if "benagalbon" not in home_norm and "benagalbon" not in away_norm:
                continue
            is_home = "benagalbon" in home_norm
            opponent = away_name if is_home else home_name
            status = "next" if is_future else "latest"
            payload = {
                "round": round_number or "",
                "date": date_iso,
                "location": "",
                "opponent": {"name": opponent.title()},
                "home": is_home,
                "status": status,
            }
            if status == "next":
                return payload
            latest_payload = payload
        if latest_payload:
            return latest_payload
    return None


def extract_next_jornada(html: str) -> Optional[int]:
    match = re.search(r"IrA\((\d+)\)", html)
    if match:
        return int(match.group(1))
    return None


def fetch_schedule(jornada: int) -> Optional[dict]:
    if not jornada:
        return None
    url = SCHEDULE_TEMPLATE.format(jornada=jornada)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-ES,es;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return parse_schedule(response.text, jornada)


def parse_schedule(html: str, jornada: int) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h3")
    date_iso = None
    if heading:
        date_match = re.search(r"\((\d{2}-\d{2}-\d{4})\)", heading.text)
        if date_match:
            try:
                date_iso = datetime.strptime(date_match.group(1), "%d-%m-%Y").date().isoformat()
            except ValueError:
                date_iso = None
    table = soup.select_one("table")
    if not table:
        return None
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        home_name = cells[0].get_text(" ", strip=True)
        away_name = cells[2].get_text(" ", strip=True)
        home_norm = normalize_text(home_name)
        away_norm = normalize_text(away_name)
        if "benagalbon" not in home_norm and "benagalbon" not in away_norm:
            continue
        is_home = "benagalbon" in home_norm
        opponent = away_name if is_home else home_name
        return {
            "round": f"{jornada}",
            "date": date_iso,
            "location": "",
            "opponent": {"name": opponent.title()},
            "home": is_home,
            "status": "next",
        }
    return None


def save_next_match_cache(payload: Optional[Dict[str, str]]):
    if not payload:
        if NEXT_MATCH_FILE.exists():
            NEXT_MATCH_FILE.unlink()
        return
    NEXT_MATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NEXT_MATCH_FILE.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def write_csv(rows: List[dict]):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def import_csv():
    subprocess.run(
        ["python", "manage.py", "import_standings", str(OUTPUT)],
        cwd=str(BASE_DIR),
        check=True,
    )


def main():
    print("Descargando tabla oficial desde la RFAF…")
    rows, html = parse_table()
    next_match = extract_next_match_from_classification(html)
    if not next_match:
        next_jornada = extract_next_jornada(html)
        next_match = fetch_schedule(next_jornada) if next_jornada else None
    save_next_match_cache(next_match)
    print(f"Guardando CSV en {OUTPUT}")
    write_csv(rows)
    print("Importando a Django…")
    import_csv()
    print("Clasificación actualizada desde la federación.")


if __name__ == "__main__":
    main()
