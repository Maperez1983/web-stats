import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _to_date_iso(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _safe_get(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _absolute_url(url: Any, base: str = "https://www.rfaf.es") -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return f"{base}{raw}"
    return raw


def _iter_nodes(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_nodes(item)


def _looks_like_standings_list(items: List[Any]) -> bool:
    if not items or not isinstance(items[0], dict):
        return False
    sample = items[0]
    keys = {_normalize_text(k) for k in sample.keys()}
    has_team = any(k in keys for k in ("team", "equipo", "club", "nombre"))
    has_rank = any(k in keys for k in ("position", "posicion", "puesto", "rank", "orden"))
    has_points = any(k in keys for k in ("points", "puntos", "pts", "pt"))
    return has_team and (has_rank or has_points)


def _looks_like_player_stats_list(items: List[Any]) -> bool:
    if not items or not isinstance(items[0], dict):
        return False
    sample = items[0]
    keys = {_normalize_text(k) for k in sample.keys()}
    has_name = any(k in keys for k in ("name", "nombre", "jugador", "player"))
    has_stats = any(
        k in keys
        for k in (
            "pj",
            "partidos",
            "minutes",
            "minutos",
            "goals",
            "goles",
            "yellow_cards",
            "amarillas",
            "tarjetas",
        )
    )
    return has_name and has_stats


def _extract_standings(captures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Preferred path: explicit classification endpoint.
    best_payload = None
    best_round = -1
    for item in captures:
        url = str(item.get("url") or "")
        if not url.endswith("/api/novanet/competition/get-classification"):
            continue
        payload = item.get("json")
        if not isinstance(payload, dict):
            continue
        rows = payload.get("clasificacion")
        if not isinstance(rows, list) or not rows:
            continue
        round_raw = str(payload.get("jornada") or "").strip()
        try:
            round_num = int(re.sub(r"[^0-9]", "", round_raw) or 0)
        except ValueError:
            round_num = 0
        if round_num >= best_round:
            best_round = round_num
            best_payload = payload

    if isinstance(best_payload, dict):
        standings = []
        for row in best_payload.get("clasificacion") or []:
            if not isinstance(row, dict):
                continue
            standings.append(
                {
                    "position": _safe_get(row, "posicion", "position", "rank"),
                    "team": _safe_get(row, "nombre", "team", "equipo"),
                    "crest_url": _absolute_url(_safe_get(row, "url_img", "escudo", "logo")),
                    "team_code": str(_safe_get(row, "codequipo", "cod_equipo", "team_code") or "").strip(),
                    "points": _safe_get(row, "puntos", "points", "pts"),
                    "played": _safe_get(row, "jugados", "played", "pj"),
                    "wins": _safe_get(row, "ganados", "wins", "pg"),
                    "draws": _safe_get(row, "empatados", "draws", "pe"),
                    "losses": _safe_get(row, "perdidos", "losses", "pp"),
                    "goals_for": _safe_get(row, "goles_a_favor", "goals_for", "gf"),
                    "goals_against": _safe_get(row, "goles_en_contra", "goals_against", "gc"),
                }
            )
        if standings:
            return standings

    # Generic fallback.
    for item in captures:
        payload = item.get("json")
        if payload is None:
            continue
        for node in _iter_nodes(payload):
            if isinstance(node, list) and _looks_like_standings_list(node):
                rows = []
                for row in node:
                    rows.append(
                        {
                            "position": _safe_get(row, "position", "posicion", "rank", "puesto", "orden"),
                            "team": _safe_get(row, "team", "equipo", "club", "nombre"),
                            "crest_url": _absolute_url(_safe_get(row, "url_img", "escudo", "logo")),
                            "team_code": str(_safe_get(row, "codequipo", "cod_equipo", "team_code") or "").strip(),
                            "points": _safe_get(row, "points", "puntos", "pts", "pt"),
                            "played": _safe_get(row, "played", "jugados", "pj", "matches"),
                            "wins": _safe_get(row, "wins", "pg", "ganados"),
                            "draws": _safe_get(row, "draws", "pe", "empatados"),
                            "losses": _safe_get(row, "losses", "pp", "perdidos"),
                            "goals_for": _safe_get(row, "goals_for", "gf", "goles_favor"),
                            "goals_against": _safe_get(row, "goals_against", "gc", "goles_contra"),
                        }
                    )
                return rows
    return []


def _extract_player_stats(captures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    players_by_code: Dict[str, Dict[str, Any]] = {}

    for item in captures:
        url = str(item.get("url") or "")
        payload = item.get("json")
        if not isinstance(payload, dict):
            continue
        if not url.endswith("/api/novanet/player/get-player-general-stats"):
            continue
        if str(payload.get("estado") or "") != "1":
            continue

        code = str(payload.get("codigo_jugador") or "").strip()
        if not code:
            continue

        name = str(payload.get("nombre_jugador") or "").strip()
        if not name:
            continue

        partidos_map = {}
        for entry in payload.get("partidos") or []:
            if isinstance(entry, dict):
                partidos_map[_normalize_text(entry.get("nombre"))] = str(entry.get("valor") or "").strip()

        tarjetas_map = {}
        for entry in payload.get("tarjetas") or []:
            if isinstance(entry, dict):
                tarjetas_map[_normalize_text(entry.get("nombre"))] = str(entry.get("valor") or "").strip()

        player_row = {
            "code": code,
            "name": name,
            "team": str(payload.get("equipo") or "").strip(),
            "team_code": str(payload.get("codigo_equipo") or "").strip(),
            "pj": partidos_map.get("jugados", partidos_map.get("partidos jugados", "0")) or "0",
            "pt": partidos_map.get("titular", "0") or "0",
            "convocados": partidos_map.get("convocados", "0") or "0",
            "minutes": str(payload.get("minutos_totales_jugados") or "").strip() or "0",
            "goals": partidos_map.get("total goles", partidos_map.get("goles", "0")) or "0",
            "yellow_cards": tarjetas_map.get("amarillas", "0") or "0",
            "red_cards": tarjetas_map.get("rojas", "0") or "0",
            "season": str(payload.get("nombre_temporada") or "").strip(),
            "category": str(payload.get("categoria_equipo") or "").strip(),
            "position": str(payload.get("posicion_jugador") or "").strip(),
            "dorsal": str(payload.get("dorsal_jugador") or "").strip(),
            "age": str(payload.get("edad") or "").strip(),
        }

        existing = players_by_code.get(code)
        if not existing:
            players_by_code[code] = player_row
            continue

        # Keep row with more complete metrics.
        def _score(row: Dict[str, Any]) -> int:
            fields = ("pj", "minutes", "goals", "yellow_cards", "red_cards")
            return sum(1 for f in fields if str(row.get(f, "")).strip() not in ("", "0"))

        if _score(player_row) >= _score(existing):
            players_by_code[code] = player_row

    if players_by_code:
        return list(players_by_code.values())

    # Generic fallback (other endpoints)
    for item in captures:
        payload = item.get("json")
        if payload is None:
            continue
        for node in _iter_nodes(payload):
            if isinstance(node, list) and _looks_like_player_stats_list(node):
                players = []
                for row in node:
                    players.append(
                        {
                            "name": _safe_get(row, "name", "nombre", "player", "jugador"),
                            "pj": _safe_get(row, "pj", "partidos", "played"),
                            "minutes": _safe_get(row, "minutes", "minutos"),
                            "goals": _safe_get(row, "goals", "goles"),
                            "yellow_cards": _safe_get(row, "yellow_cards", "amarillas", "tarjetas_amarillas"),
                            "red_cards": _safe_get(row, "red_cards", "rojas", "tarjetas_rojas"),
                        }
                    )
                return players
    return []


def _extract_candidate_player_ids(captures: List[Dict[str, Any]]) -> List[str]:
    ids = set()
    key_candidates = (
        "codigo_jugador",
        "id_player",
        "id_jugador",
        "player_id",
        "cod_jugador",
    )
    for item in captures:
        payload = item.get("json")
        if not payload:
            continue
        for node in _iter_nodes(payload):
            if not isinstance(node, dict):
                continue
            for key in key_candidates:
                value = node.get(key)
                if value is None:
                    continue
                raw = str(value).strip()
                if raw.isdigit():
                    ids.add(raw)
    return sorted(ids)


def _find_next_match(captures: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # Preferred path: explicit calendar endpoint.
    for item in captures:
        url = str(item.get("url") or "")
        if not url.endswith("/api/novanet/match/get-calendar-team"):
            continue
        payload = item.get("json")
        if not isinstance(payload, dict):
            continue
        proximo = payload.get("proximo")
        if not isinstance(proximo, dict):
            continue
        date_iso = _to_date_iso(_safe_get(proximo, "fecha", "date"))
        if not date_iso:
            continue
        home_team = _safe_get(proximo, "equipo_local", "local", "home")
        away_team = _safe_get(proximo, "equipo_visitante", "visitante", "away")
        home_norm = _normalize_text(home_team)
        away_norm = _normalize_text(away_team)
        is_home = "benagalbon" in home_norm if (home_norm or away_norm) else None
        opponent = away_team if is_home else home_team
        if not opponent:
            opponent = _safe_get(proximo, "rival", "opponent")
        opponent_crest = (
            _safe_get(proximo, "url_img_visitante", "escudo_visitante")
            if is_home
            else _safe_get(proximo, "url_img_local", "escudo_local")
        )
        return {
            "round": str(_safe_get(proximo, "jornada", "round") or "").strip(),
            "date": date_iso,
            "time": str(_safe_get(proximo, "hora", "time") or "").strip(),
            "opponent": {
                "name": str(opponent or "").strip() or "Rival por confirmar",
                "full_name": str(opponent or "").strip() or "Rival por confirmar",
                "crest_url": _absolute_url(opponent_crest),
            },
            "home": is_home,
            "source_url": url,
            "status": "next",
        }

    # Preferred fallback: results endpoint includes matchday fixture list.
    results_candidates = []
    today = date.today()
    for item in captures:
        url = str(item.get("url") or "")
        if not url.endswith("/api/novanet/match/get-results"):
            continue
        payload = item.get("json")
        if not isinstance(payload, dict):
            continue
        jornada = str(_safe_get(payload, "jornada", "nombre_jornada", "round") or "").strip()
        partidos = payload.get("partidos")
        if not isinstance(partidos, list):
            continue
        for match in partidos:
            if not isinstance(match, dict):
                continue
            home_team = _safe_get(match, "Nombre_equipo_local", "equipo_local", "local", "home")
            away_team = _safe_get(match, "Nombre_equipo_visitante", "equipo_visitante", "visitante", "away")
            home_norm = _normalize_text(home_team)
            away_norm = _normalize_text(away_team)
            bena_home = "benagalbon" in home_norm
            bena_away = "benagalbon" in away_norm
            if not (bena_home or bena_away):
                continue
            opponent = away_team if bena_home else home_team
            date_iso = _to_date_iso(_safe_get(match, "fecha", "date"))
            if not date_iso:
                continue
            try:
                match_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
            except ValueError:
                continue
            if match_date < today:
                continue
            results_candidates.append(
                {
                    "round": jornada,
                    "date": date_iso,
                    "time": str(_safe_get(match, "hora", "time") or "").strip(),
                    "opponent": {
                        "name": str(opponent or "").strip() or "Rival por confirmar",
                        "full_name": str(opponent or "").strip() or "Rival por confirmar",
                        "crest_url": _absolute_url(
                            _safe_get(match, "url_img_visitante")
                            if bena_home
                            else _safe_get(match, "url_img_local")
                        ),
                    },
                    "home": bool(bena_home),
                    "source_url": url,
                    "status": "next",
                }
            )
    if results_candidates:
        results_candidates.sort(key=lambda x: (x.get("date") or "9999-12-31", x.get("time") or "99:99"))
        return results_candidates[0]

    # Generic fallback.
    candidates = []

    for item in captures:
        payload = item.get("json")
        if payload is None:
            continue
        for node in _iter_nodes(payload):
            if not isinstance(node, dict):
                continue
            keys = {_normalize_text(k) for k in node.keys()}
            likely_match = any(
                k in keys
                for k in (
                    "jornada",
                    "round",
                    "fecha",
                    "date",
                    "local",
                    "visitante",
                    "equipo_local",
                    "equipo_visitante",
                    "rival",
                    "opponent",
                )
            )
            if not likely_match:
                continue

            home_name = _safe_get(node, "home", "local", "equipo_local", "homeTeam", "home_team")
            away_name = _safe_get(node, "away", "visitante", "equipo_visitante", "awayTeam", "away_team")
            opponent_name = _safe_get(node, "opponent", "rival", "oponente")
            date_raw = _safe_get(node, "date", "fecha", "fecha_partido")
            round_raw = _safe_get(node, "round", "jornada")
            time_raw = _safe_get(node, "time", "hora")

            home_norm = _normalize_text(home_name)
            away_norm = _normalize_text(away_name)
            bena_home = "benagalbon" in home_norm
            bena_away = "benagalbon" in away_norm
            if not opponent_name and (bena_home or bena_away):
                opponent_name = away_name if bena_home else home_name

            date_iso = _to_date_iso(date_raw)
            if not date_iso:
                continue
            try:
                parsed = datetime.strptime(date_iso, "%Y-%m-%d").date()
            except ValueError:
                continue
            if parsed < today:
                continue

            if not opponent_name and not (bena_home or bena_away):
                continue

            candidates.append(
                {
                    "round": str(round_raw or "").strip(),
                    "date": date_iso,
                    "time": str(time_raw or "").strip(),
                    "opponent": {
                        "name": str(opponent_name or "").strip() or "Rival por confirmar",
                        "full_name": str(opponent_name or "").strip() or "Rival por confirmar",
                        "crest_url": _absolute_url(
                            _safe_get(node, "url_img_visitante")
                            if bena_home
                            else _safe_get(node, "url_img_local")
                        ),
                    },
                    "home": bool(bena_home) if (bena_home or bena_away) else None,
                    "source_url": item.get("url"),
                }
            )

    if not candidates:
        return None
    candidates.sort(key=lambda x: x.get("date") or "9999-12-31")
    best = candidates[0]
    best["status"] = "next"
    return best


class Command(BaseCommand):
    help = (
        "Captura respuestas API de Universo RFAF usando storage_state autenticado y genera "
        "un snapshot heurístico (próximo rival, clasificación y jugadores)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dashboard-url",
            default="https://www.universorfaf.es/dashboard",
            help="URL autenticada principal (dashboard).",
        )
        parser.add_argument(
            "--results-url",
            default="https://www.universorfaf.es/competitions/results/0",
            help="URL de resultados para capturar endpoints de clasificación/partidos.",
        )
        parser.add_argument(
            "--team-url",
            default="",
            help=(
                "URL de equipo (ej. /team/834315?...). "
                "Si se indica, se intenta capturar estadísticas de toda la plantilla."
            ),
        )
        parser.add_argument(
            "--storage-state",
            default=str(Path("data") / "input" / "rfaf_storage_state.json"),
            help="Ruta al storage_state generado en login manual.",
        )
        parser.add_argument(
            "--wait-ms",
            type=int,
            default=12000,
            help="Tiempo de espera tras abrir dashboard para capturar llamadas XHR/fetch.",
        )
        parser.add_argument(
            "--manual-browse-ms",
            type=int,
            default=0,
            help=(
                "Espera adicional en resultados para interacción manual (ms). "
                "Útil para hacer clic en competición/jornada y disparar endpoints."
            ),
        )
        parser.add_argument(
            "--capture-out",
            default=str(Path("data") / "input" / "universo-rfaf-capture.json"),
            help="Archivo JSON con capturas crudas de red.",
        )
        parser.add_argument(
            "--snapshot-out",
            default=str(Path("data") / "input" / "universo-rfaf-snapshot.json"),
            help="Archivo JSON con snapshot estructurado.",
        )
        parser.add_argument("--headed", action="store_true", help="Ejecuta Chromium visible.")

    def handle(self, *args, **options):
        storage_state_path = Path(options["storage_state"]).expanduser()
        if not storage_state_path.exists():
            raise CommandError(f"No existe storage_state: {storage_state_path}")

        dashboard_url = str(options["dashboard_url"]).strip()
        results_url = str(options["results_url"]).strip()
        team_url = str(options.get("team_url") or "").strip()
        parsed_target = urlparse(dashboard_url)
        if not parsed_target.scheme or not parsed_target.netloc:
            raise CommandError(f"URL de dashboard inválida: {dashboard_url}")
        parsed_results = urlparse(results_url)
        if not parsed_results.scheme or not parsed_results.netloc:
            raise CommandError(f"URL de resultados inválida: {results_url}")
        if parsed_results.netloc != parsed_target.netloc:
            raise CommandError("results-url debe tener el mismo dominio que dashboard-url.")
        parsed_team = None
        if team_url:
            parsed_team = urlparse(team_url)
            if not parsed_team.scheme or not parsed_team.netloc:
                raise CommandError(f"URL de equipo inválida: {team_url}")
            if parsed_team.netloc != parsed_target.netloc:
                raise CommandError("team-url debe tener el mismo dominio que dashboard-url.")

        wait_ms = int(options["wait_ms"])
        manual_browse_ms = int(options["manual_browse_ms"])
        capture_out = Path(options["capture_out"]).expanduser()
        snapshot_out = Path(options["snapshot_out"]).expanduser()
        headless = not bool(options["headed"])

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise CommandError(
                "No se pudo importar Playwright. Instala: pip install playwright && python -m playwright install chromium"
            ) from exc

        captures: List[Dict[str, Any]] = []
        target_team_id = ""
        if team_url:
            match = re.search(r"/team/(\d+)", team_url)
            if match:
                target_team_id = match.group(1)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(storage_state=str(storage_state_path), locale="es-ES")
            page = context.new_page()

            def _on_response(response):
                try:
                    req = response.request
                    if req.resource_type not in ("xhr", "fetch"):
                        return
                    url = response.url or ""
                    parsed = urlparse(url)
                    if parsed.netloc != parsed_target.netloc:
                        return
                    ctype = (response.header_value("content-type") or "").lower()
                    if ("json" not in ctype) and ("/api/" not in parsed.path.lower()):
                        return
                    payload_json = None
                    payload_text = None
                    try:
                        payload_json = response.json()
                    except Exception:
                        try:
                            payload_text = response.text()
                        except Exception:
                            payload_text = None
                    captures.append(
                        {
                            "url": url,
                            "status": response.status,
                            "method": req.method,
                            "resource_type": req.resource_type,
                            "content_type": ctype,
                            "request_post_data": req.post_data,
                            "json": payload_json,
                            "text": payload_text[:2000] if isinstance(payload_text, str) else None,
                        }
                    )
                except Exception:
                    return

            page.on("response", _on_response)

            try:
                page.goto(dashboard_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(wait_ms)
                page.goto(results_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(wait_ms)
                if team_url:
                    page.goto(team_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(wait_ms)
                    try:
                        dom_ids = page.evaluate(
                            """() => {
                                const ids = new Set();
                                const fromHref = (value) => {
                                    const m = String(value || '').match(/\\/player\\/(\\d+)/);
                                    if (m) ids.add(m[1]);
                                };
                                document.querySelectorAll('a[href*="/player/"]').forEach((el) => fromHref(el.getAttribute('href')));
                                document.querySelectorAll('[data-player-id],[data-id-player],[data-id_jugador]').forEach((el) => {
                                    const raw = el.getAttribute('data-player-id') || el.getAttribute('data-id-player') || el.getAttribute('data-id_jugador');
                                    if (raw && /^\\d+$/.test(raw)) ids.add(raw);
                                });
                                return Array.from(ids);
                            }"""
                        ) or []
                    except Exception:
                        dom_ids = []

                    for pid in dom_ids[:120]:
                        try:
                            page.evaluate(
                                """async (playerId) => {
                                    const form = new FormData();
                                    form.append('id_player', String(playerId));
                                    await fetch('/api/novanet/player/get-player-general-stats', {
                                        method: 'POST',
                                        body: form,
                                        credentials: 'include',
                                    });
                                }""",
                                pid,
                            )
                            page.wait_for_timeout(150)
                        except Exception:
                            continue
                    page.wait_for_timeout(1200)

                    api_ids = _extract_candidate_player_ids(captures)
                    for pid in api_ids[:200]:
                        try:
                            page.evaluate(
                                """async (playerId) => {
                                    const form = new FormData();
                                    form.append('id_player', String(playerId));
                                    await fetch('/api/novanet/player/get-player-general-stats', {
                                        method: 'POST',
                                        body: form,
                                        credentials: 'include',
                                    });
                                }""",
                                pid,
                            )
                            page.wait_for_timeout(80)
                        except Exception:
                            continue
                    page.wait_for_timeout(1200)
                if manual_browse_ms > 0:
                    self.stdout.write(
                        f"Modo interacción manual activo: {manual_browse_ms}ms en {results_url}"
                    )
                    page.wait_for_timeout(manual_browse_ms)
            finally:
                context.close()
                browser.close()

        if not captures:
            raise CommandError(
                "No se capturaron respuestas API. Revisa si la sesión expiró y regenera storage_state."
            )

        capture_out.parent.mkdir(parents=True, exist_ok=True)
        capture_out.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now().isoformat(),
                    "dashboard_url": dashboard_url,
                    "results_url": results_url,
                    "count": len(captures),
                    "items": captures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        standings = _extract_standings(captures)
        next_match = _find_next_match(captures)
        players = _extract_player_stats(captures)
        if target_team_id:
            players = [p for p in players if str(p.get("team_code") or "").strip() == target_team_id]
        snapshot = {
            "captured_at": datetime.now().isoformat(),
            "source": "universo-rfaf",
            "team_url": team_url or None,
            "team_id": target_team_id or None,
            "next_match": next_match,
            "standings": standings,
            "players": players,
        }
        snapshot_out.parent.mkdir(parents=True, exist_ok=True)
        snapshot_out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Capturas guardadas: {capture_out} ({len(captures)} items)"))
        self.stdout.write(
            self.style.SUCCESS(
                "Snapshot guardado: "
                f"{snapshot_out} | next_match={'sí' if next_match else 'no'} "
                f"| standings={len(standings)} | players={len(players)}"
            )
        )
