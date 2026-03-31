import csv
import json
import os
import re
import subprocess
import sys
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
FALLBACK_HTML = Path(
    os.getenv("RFAF_FALLBACK_HTML", str(BASE_DIR / "data" / "input" / "rfaf-fallback.html"))
)
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
ALLOW_FALLBACK_HTML = str(os.getenv("RFAF_ALLOW_FALLBACK_HTML", "0")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

BASE_ORIGIN = "https://www.rfaf.es"


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


def fetch_html(*, allow_fallback: bool = False) -> str:
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
        if allow_fallback and FALLBACK_HTML.exists():
            return FALLBACK_HTML.read_text(encoding="utf-8")
        raise


def parse_table(*, allow_fallback: bool = False) -> (List[dict], str):
    html = fetch_html(allow_fallback=allow_fallback)
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
    today = datetime.now().date()
    candidates: List[Dict[str, str]] = []
    # Resultado típico: "2-1" (sin texto adicional). Evitamos falsos positivos con fechas tipo "29-03-2026".
    result_pattern = re.compile(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$")
    time_pattern = re.compile(r"\b\d{1,2}:\d{2}\b")
    for heading in blocks:
        text = heading.get_text(strip=True)
        round_match = re.search(r"Jornada\s*(\d+)", text, re.IGNORECASE)
        date_match = re.search(r"\((\d{2}[/-]\d{2}[/-]\d{4})\)", text)
        round_number = round_match.group(1) if round_match else None
        date_iso = None
        if date_match:
            try:
                raw_date = date_match.group(1).replace("/", "-")
                date_iso = datetime.strptime(raw_date, "%d-%m-%Y").date().isoformat()
            except ValueError:
                date_iso = None
        table = heading.find_next("table")
        if not table:
            continue
        for row in table.select("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            home_name = cells[0].get_text(" ", strip=True)
            score_text = cells[1].get_text(" ", strip=True)
            away_name = cells[2].get_text(" ", strip=True)
            home_norm = normalize_text(home_name)
            away_norm = normalize_text(away_name)
            # En RFAF el "marcador" para partidos futuros suele ser la hora (p.e. 18:00),
            # que contiene dígitos pero NO es un resultado. Detectamos resultados explícitos "1-0".
            is_future = not bool(result_pattern.match(score_text or ""))
            if "benagalbon" not in home_norm and "benagalbon" not in away_norm:
                continue
            is_home = "benagalbon" in home_norm
            opponent = away_name if is_home else home_name
            status = "next" if is_future else "latest"
            payload = {
                "round": round_number or "",
                "date": date_iso,
                "time": (time_pattern.search(score_text).group(0) if time_pattern.search(score_text) else ""),
                "location": "",
                "opponent": {"name": opponent.title()},
                "home": is_home,
                "status": status,
            }
            if status == "next":
                candidates.append(payload)
    if not candidates:
        return None

    def _candidate_sort_key(item: Dict[str, str]):
        raw_date = item.get("date")
        parsed = None
        if raw_date:
            try:
                parsed = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except ValueError:
                parsed = None
        # Prefer upcoming dates >= today; then undated; finally stale past dates.
        if parsed and parsed >= today:
            return (0, parsed.toordinal())
        if parsed is None:
            return (1, 0)
        return (2, parsed.toordinal())

    best = sorted(candidates, key=_candidate_sort_key)[0]
    best_date = best.get("date")
    if best_date:
        try:
            if datetime.strptime(str(best_date), "%Y-%m-%d").date() < today:
                return None
        except ValueError:
            return None
    return best


def _extract_schedule_template(html: str):
    """
    Extrae una URL de jornada desde la propia página de clasificación.
    Ejemplo embebido:
      /pnfg/NPcd/NFG_CmpJornada?...&CodJornada=27
    """
    if not html:
        return None, None
    match = re.search(
        r'(/pnfg/NPcd/NFG_CmpJornada\?[^"\']*?(?:CodJornada|codjornada)=(\d+))',
        html,
        re.IGNORECASE,
    )
    if not match:
        return None, None
    url = match.group(1)
    try:
        current_round = int(match.group(2))
    except ValueError:
        current_round = None
    template = re.sub(r'(?:CodJornada|codjornada)=\d+', 'CodJornada={jornada}', url, flags=re.IGNORECASE)
    return template, current_round


def fetch_next_match_from_classification(html: str, *, max_checks: int = 8) -> Optional[dict]:
    """
    Fallback robusto: si la página de clasificación no trae el cuadro de partidos,
    buscamos el próximo partido iterando jornadas (NFG_CmpJornada) a partir de la actual.
    """
    template, current_round = _extract_schedule_template(html or "")
    # Incluimos la jornada actual: puede haber partidos "Suspendidos/Aplazados" aún pendientes.
    start_round = current_round if isinstance(current_round, int) else None
    if not start_round:
        start_round = extract_next_jornada(html) if html else None
    if not start_round:
        return None
    for offset in range(max_checks):
        jornada = int(start_round) + offset
        payload = fetch_schedule(jornada, template=template) if template else fetch_schedule(jornada)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("status") or "").strip().lower() != "next":
            continue
        return payload
    return None


def extract_next_jornada(html: str) -> Optional[int]:
    # Intentar inferir la próxima jornada desde la tabla (PJ del Benagalbón + 1).
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = (
            soup.select_one("#CL_Detalle table.table.table-striped")
            or soup.select_one("#CL_Detalle table")
            or soup.select_one("#CL_Resumen table.table.table-striped")
        )
        if table:
            for row in table.select("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) < 14:
                    continue
                team_name = _team_text(cells[2])
                if "benagalbon" not in normalize_text(team_name):
                    continue
                home_j = _parse_int(cells[4].get_text(strip=True))
                away_j = _parse_int(cells[8].get_text(strip=True))
                played = home_j + away_j
                if played > 0:
                    return played + 1
    except Exception:
        pass
    match = re.search(r"IrA\((\d+)\)", html)
    if match:
        return int(match.group(1))
    match = re.search(r"CodJornada=(\d+)", html)
    if match:
        return int(match.group(1))
    return None


def fetch_schedule(jornada: int, template: Optional[str] = None) -> Optional[dict]:
    if not jornada:
        return None
    url = (template or SCHEDULE_TEMPLATE).format(jornada=jornada)
    if url.startswith("/"):
        url = f"{BASE_ORIGIN}{url}"
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
    # Resultado típico: "2-1" (sin texto adicional). Evitamos falsos positivos con fechas.
    result_pattern = re.compile(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$")
    date_in_cell = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")
    time_in_cell = re.compile(r"\b(\d{1,2}:\d{2})\b")
    today = datetime.now().date()
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        # Algunas tablas traen una primera celda "combinada" y luego (local, estado/resultado, visitante, campo).
        # Otras vienen en formato simple (local, estado/resultado, visitante).
        cell_texts = [cell.get_text(" ", strip=True) for cell in cells]
        if len(cell_texts) >= 4 and (
            "benagalbon" in normalize_text(cell_texts[1])
            or "benagalbon" in normalize_text(cell_texts[3])
        ):
            home_name = cell_texts[1]
            middle_text = cell_texts[2] if len(cell_texts) > 2 else ""
            away_name = cell_texts[3] if len(cell_texts) > 3 else ""
            location = cell_texts[4] if len(cell_texts) > 4 else ""
        else:
            home_name = cell_texts[0]
            middle_text = cell_texts[1] if len(cell_texts) > 1 else ""
            away_name = cell_texts[2] if len(cell_texts) > 2 else ""
            location = cell_texts[3] if len(cell_texts) > 3 else ""
        home_norm = normalize_text(home_name)
        away_norm = normalize_text(away_name)
        if "benagalbon" not in home_norm and "benagalbon" not in away_norm:
            continue
        is_home = "benagalbon" in home_norm
        opponent = away_name if is_home else home_name
        status = "latest" if result_pattern.match(middle_text or "") else "next"
        time_label = ""
        time_match = time_in_cell.search(middle_text or "")
        if time_match:
            time_label = time_match.group(1)
        # Preferimos la fecha del encabezado; si no existe, intentamos extraerla de la celda central.
        final_date_iso = date_iso
        if not final_date_iso:
            date_match = date_in_cell.search(middle_text or "")
            if date_match:
                raw = date_match.group(1).replace("/", "-")
                try:
                    final_date_iso = datetime.strptime(raw, "%d-%m-%Y").date().isoformat()
                except ValueError:
                    final_date_iso = None
        # Si el partido está aplazado/suspendido, no usamos una fecha pasada como "indicador de ya jugado".
        if status == "next" and final_date_iso:
            try:
                parsed_date = datetime.strptime(final_date_iso, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = None
            if parsed_date and parsed_date < today and re.search(r"(suspendid|aplazad|pendient)", middle_text.lower()):
                final_date_iso = None
        return {
            "round": f"{jornada}",
            "date": final_date_iso,
            "time": time_label,
            "location": location,
            "opponent": {"name": opponent.title()},
            "home": is_home,
            "status": status,
            "source": "rfaf",
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
        [sys.executable, "manage.py", "import_standings", str(OUTPUT)],
        cwd=str(BASE_DIR),
        check=True,
        timeout=120,
    )


def main():
    print("Descargando tabla oficial desde la RFAF…")
    rows, html = parse_table(allow_fallback=ALLOW_FALLBACK_HTML)
    next_match = extract_next_match_from_classification(html)
    if not next_match:
        next_match = fetch_next_match_from_classification(html)
    if next_match and next_match.get("status") != "next":
        next_match = None
    save_next_match_cache(next_match)
    print(f"Guardando CSV en {OUTPUT}")
    write_csv(rows)
    print("Importando a Django…")
    import_csv()
    print("Clasificación actualizada desde la federación.")


if __name__ == "__main__":
    main()
