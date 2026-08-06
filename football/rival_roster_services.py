"""Importación de plantillas RIVALES desde laPreferente hacia el modelo aislado RivalPlayer.

- `parse_rival_squad(html)`: parser correcto de la tabla de plantilla (#tablePlantilla). El parser
  general `services.parse_preferente_roster` desalinea columnas en esta página (coge el dorsal como
  posición y pierde el id de jugador), así que aquí extraemos con anclaje en la celda del enlace del
  jugador: J-id, dorsal, alias, nombre completo, posición, edad, foto y stats de temporada.
- `import_rival_squad(rival_team, rows, ...)`: upsert de RivalPlayer por J-id (dedup estable, sin
  duplicar entre refrescos ni entre equipos), detección "reconocido como" contra Players existentes
  (ex-jugador propio u ojeado que ha fichado por un rival) SIN fusionar, y baja de los que ya no están.

Nada de esto toca Player ni la plantilla propia: RivalPlayer es un modelo aislado para análisis.
"""
import re

from bs4 import BeautifulSoup

from .models import Player, RivalPlayer

PREFERENTE_BASE = "https://lapreferente.com/"

_J_ID_RE = re.compile(r"J(\d+)C", re.IGNORECASE)
_PHOTO_RE = re.compile(r"jugadores/.*?(\d+)-mini", re.IGNORECASE)


def _position_line(position_text):
    """Mapea la demarcación cruda de laPreferente a línea gk/def/mid/att."""
    p = str(position_text or "").strip().lower()
    if not p:
        return "mid"
    if "portero" in p:
        return "gk"
    if any(k in p for k in ("lateral", "central", "defensa", "carrilero", "líbero", "libero")):
        return "def"
    if any(k in p for k in ("extremo", "delantero", "punta", "ariete", "mediapunta")):
        return "att"
    if any(k in p for k in ("medio", "centrocampista", "pivote", "interior", "volante", "mediocentro")):
        return "mid"
    return "mid"


def _to_int(value):
    if value is None:
        return None
    m = re.search(r"-?\d+", str(value))
    return int(m.group(0)) if m else None


def _abs_url(href):
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return PREFERENTE_BASE + href.lstrip("/")


def parse_rival_squad(html):
    """Devuelve [{source_player_id, profile_url, full_name, alias, number, age, position, line,
    photo_url, matches_played, minutes, goals, yellow_cards, red_cards}] a partir del HTML de la
    ficha de equipo de laPreferente. Solo filas que son jugadores reales (tienen enlace J-id)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tablePlantilla")
    if table is None:
        for cand in soup.find_all("table"):
            head = cand.find("tr")
            if not head:
                continue
            htxt = " ".join(c.get_text(" ", strip=True).lower() for c in head.find_all(["th", "td"]))
            if "jugador" in htxt and "min" in htxt:
                table = cand
                break
    if table is None:
        return []

    players = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 9:
            continue
        # Anclaje: la celda del jugador es la que contiene el enlace J<id>C...
        name_idx = None
        jid = ""
        profile_url = ""
        for idx, cell in enumerate(cells):
            link = cell.find("a", href=True)
            if link and _J_ID_RE.search(link["href"]):
                name_idx = idx
                m = _J_ID_RE.search(link["href"])
                jid = m.group(1)
                profile_url = _abs_url(link["href"])
                break
        if name_idx is None:
            continue  # cabecera de grupo (Porteros (2)...) u otra fila sin jugador

        name_cell = cells[name_idx]
        texts = [t.strip() for t in name_cell.stripped_strings if t.strip()]
        alias = texts[0] if texts else ""
        # El nombre completo es el texto más largo (o el segundo); alias suele ser un prefijo.
        full_name = max(texts, key=len) if texts else alias
        if full_name == alias and len(texts) > 1:
            full_name = texts[-1]

        number = _to_int(cells[name_idx - 1].get_text(strip=True)) if name_idx >= 1 else None
        position = cells[name_idx + 1].get_text(" ", strip=True) if len(cells) > name_idx + 1 else ""

        # Las últimas 7 celdas son las stats de temporada: PC, PJ, PT, Min, Goles, TA, TR.
        stats = [c.get_text(" ", strip=True) for c in cells[-7:]]
        pj = _to_int(stats[1]) if len(stats) > 1 else None
        minutes = _to_int(stats[3]) if len(stats) > 3 else None
        goals = _to_int(stats[4]) if len(stats) > 4 else None
        ta = _to_int(stats[5]) if len(stats) > 5 else None
        tr = _to_int(stats[6]) if len(stats) > 6 else None
        # La edad es la celda inmediatamente anterior a las stats.
        age = _to_int(cells[-8].get_text(strip=True)) if len(cells) >= 8 else None

        photo_url = ""
        for img in row.find_all("img"):
            src = img.get("src") or ""
            if "-mini" in src or _PHOTO_RE.search(src):
                if "sin-foto" not in src:
                    photo_url = _abs_url(src)
                break

        if not full_name:
            continue
        players.append({
            "source_player_id": jid,
            "profile_url": profile_url,
            "full_name": full_name[:140],
            "alias": alias[:80],
            "number": number,
            "age": age if (age is not None and age > 0) else None,
            "position": position[:60],
            "line": _position_line(position),
            "photo_url": photo_url[:300],
            "matches_played": pj or 0,
            "minutes": minutes or 0,
            "goals": goals or 0,
            "yellow_cards": ta or 0,
            "red_cards": tr or 0,
        })
    return players


def upsert_manual_rival_player(team, datos):
    """Alta de un jugador que la fuente NO lista para ese equipo. Devuelve (jugador, creado).

    Existe porque un rival de amistoso juega con gente que su ficha publicada no recoge -cedidos,
    canteranos que suben, fichajes recientes-. Se guarda con `source='manual'` para que
    `import_rival_squad` no lo desactive, y se usa desde los DOS caminos de alta (el formulario
    de la ficha y la ingesta del agente) para que no haya dos reglas distintas.
    """
    nombre = " ".join(str(datos.get("full_name") or "").split())[:140]
    if not team or not nombre:
        return None, False
    ya = RivalPlayer.objects.filter(team=team, full_name__iexact=nombre).first()
    if ya:
        return ya, False

    def _entero(valor):
        try:
            n = int(str(valor).strip())
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    posicion = " ".join(str(datos.get("position") or "").split())[:60]
    linea = str(datos.get("line") or "").strip().lower()
    if linea not in {"gk", "def", "mid", "att"}:
        linea = _position_line(posicion) or ""
    return (
        RivalPlayer.objects.create(
            team=team,
            source=RivalPlayer.SOURCE_MANUAL,
            full_name=nombre,
            alias=" ".join(str(datos.get("alias") or "").split())[:80],
            number=_entero(datos.get("number")),
            age=_entero(datos.get("age")),
            position=posicion,
            line=linea,
            photo_url=str(datos.get("photo_url") or "").strip()[:300],
            # De donde salio el dato, para poder volver a la fuente desde su ficha.
            preferente_profile_url=str(datos.get("profile_url") or "").strip()[:300],
            is_active=True,
        ),
        True,
    )


def parse_team_crest(html):
    """URL del escudo del equipo en una pagina de laPreferente, o "" si no la publica.

    La fuente lo expone en og:image, que es la unica referencia estable: los <img> del
    escudo cambian de clase cada rediseno.
    """
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html or "", re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html or "", re.I)
    url = (m.group(1) if m else "").strip()
    return url if "/escudos/" in url else ""


def _detect_matched_player(row):
    """"Reconocido como": localiza un Player ya en el sistema que sea la MISMA persona (sin fusionar).
    Prioridad: J-id en preferente_profile_url (exacto y fiable) -> nombre completo exacto -> alias
    exacto (solo si es único, para no casar por error). Devuelve Player o None."""
    jid = str(row.get("source_player_id") or "").strip()
    if jid:
        p = Player.objects.filter(preferente_profile_url__icontains=f"J{jid}C").first()
        if p:
            return p
    full_name = str(row.get("full_name") or "").strip()
    if full_name:
        p = Player.objects.filter(name__iexact=full_name).first()
        if p:
            return p
    alias = str(row.get("alias") or "").strip()
    if alias:
        cands = list(Player.objects.filter(name__iexact=alias)[:2])
        if len(cands) == 1:  # alias único -> es esa persona; si hay varios, no arriesgamos
            return cands[0]
    return None


def fetch_and_import_rival_team(*, name, preferente_url, external_id="", group=None, season_label=""):
    """Baja y importa la plantilla de UN equipo rival. Crea/resuelve el Team (dedup) y devuelve
    (team, result_dict) o (team, None) si falló la descarga/parseo (no rompe el resto de la liga)."""
    from .models import resolve_or_create_team
    from .services import _fetch_preferente_response

    team, _created = resolve_or_create_team(
        name=name or preferente_url, external_id=external_id, preferente_url=preferente_url, group=group
    )
    try:
        resp = _fetch_preferente_response(preferente_url, timeout=25)
        if getattr(resp, "status_code", None) == 403:
            return team, None
        resp.raise_for_status()
        rows = parse_rival_squad(resp.text)
    except Exception:
        return team, None
    if not rows:
        return team, None
    return team, import_rival_squad(team, rows, season_label=season_label)


def import_rival_competition(competition_url, *, season_label="", limit=None, skip_team_codes=None):
    """Importa las plantillas de TODOS los equipos de una competición de laPreferente hacia
    RivalPlayer. Lee la clasificación para obtener los equipos (nombre + código ExxxC), construye la
    URL de cada plantilla (`E{code}C{comp}-1/x` funciona sin slug) e importa cada una. Resiliente: si
    un equipo falla (403/estructura), lo salta y sigue. Devuelve un resumen por equipo + totales."""
    import re as _re

    from .preferente_competition_services import parse_preferente_standings
    from .services import _fetch_preferente_response

    comp_match = _re.search(r"C(\d+)", str(competition_url or ""))
    if not comp_match:
        raise ValueError("No pude extraer el código de competición (C…) de la URL.")
    comp_code = comp_match.group(1)

    resp = _fetch_preferente_response(competition_url, timeout=25)
    resp.raise_for_status()
    standings = parse_preferente_standings(resp.text)
    if not standings:
        raise ValueError("No pude leer la clasificación (¿HTML bloqueado o competición vacía?).")

    skip = {str(c).strip().upper() for c in (skip_team_codes or []) if str(c).strip()}
    per_team = []
    totals = {"teams": 0, "created": 0, "updated": 0, "deactivated": 0, "matched": 0, "failed": 0, "skipped": 0}
    for i, row in enumerate(standings):
        if limit is not None and i >= int(limit):
            break
        name = str(row.get("full_name") or row.get("team") or "").strip()
        code = str(row.get("team_code") or "").strip()  # ej. "E282"
        if not code:
            continue
        if code.upper() in skip:  # tu propio equipo: no es un rival
            totals["skipped"] += 1
            continue
        team_url = f"{PREFERENTE_BASE}{code}C{comp_code}-1/x"
        team, result = fetch_and_import_rival_team(
            name=name, preferente_url=team_url, external_id=code, group=None, season_label=season_label
        )
        totals["teams"] += 1
        if result is None:
            totals["failed"] += 1
            per_team.append({"name": name, "team_id": getattr(team, "id", None), "ok": False})
        else:
            for k in ("created", "updated", "deactivated", "matched"):
                totals[k] += result.get(k, 0)
            per_team.append({"name": name, "team_id": getattr(team, "id", None), "ok": True, **result})
    return {"totals": totals, "teams": per_team}


def import_rival_squad(rival_team, rows, *, season_label="", replace_missing=True):
    """Upsert de RivalPlayer para un equipo rival. Dedup por J-id (o nombre si no hay J-id). Detecta
    'reconocido como' contra Players. Da de baja (is_active=False) los que ya no aparecen. Nunca crea
    ni modifica Player. Devuelve {created, updated, deactivated, matched}."""
    if not rival_team:
        return {"created": 0, "updated": 0, "deactivated": 0, "matched": 0}
    created = updated = matched = 0
    seen_ids = set()
    for row in rows or []:
        sid = str(row.get("source_player_id") or "").strip()
        full_name = str(row.get("full_name") or "").strip()
        if not full_name:
            continue
        lookup = {"team": rival_team}
        if sid:
            lookup["source_player_id"] = sid
        else:
            lookup["full_name"] = full_name
        matched_player = _detect_matched_player(row)
        if matched_player:
            matched += 1
        defaults = {
            "full_name": full_name,
            "alias": row.get("alias") or "",
            "number": row.get("number"),
            "age": row.get("age"),
            "position": row.get("position") or "",
            "line": row.get("line") or "mid",
            "photo_url": row.get("photo_url") or "",
            "preferente_profile_url": row.get("profile_url") or "",
            "matches_played": row.get("matches_played") or 0,
            "minutes": row.get("minutes") or 0,
            "goals": row.get("goals") or 0,
            "yellow_cards": row.get("yellow_cards") or 0,
            "red_cards": row.get("red_cards") or 0,
            "season_label": season_label or "",
            "matched_player": matched_player,
            "is_active": True,
        }
        if sid:
            defaults["source_player_id"] = sid
        obj, was_created = RivalPlayer.objects.update_or_create(defaults=defaults, **lookup)
        seen_ids.add(obj.id)
        created += 1 if was_created else 0
        updated += 0 if was_created else 1
    deactivated = 0
    if replace_missing:
        # Los jugadores dados de alta a mano NO se tocan: la fuente no los conoce y, sin esto,
        # la importacion semanal los daria de baja en cuanto pasara por ese equipo.
        stale = (
            RivalPlayer.objects.filter(team=rival_team, is_active=True)
            .exclude(id__in=seen_ids)
            .exclude(source=RivalPlayer.SOURCE_MANUAL)
        )
        deactivated = stale.count()
        stale.update(is_active=False)
    return {"created": created, "updated": updated, "deactivated": deactivated, "matched": matched}
