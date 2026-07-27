"""Sincroniza el calendario/resultados de la competición (Universo RFAF) hacia objetos `Match`
locales, para no tener que dar de alta los partidos a mano.

Reutiliza la MISMA forma de payload que ya lee el resto de la app (partidos por jornada con
`Goles_casa`/`Goles_visitante`, `Nombre_equipo_local/visitante`, `CodEquipo_*`, `fecha`).

Diseño defensivo:
- `write=False` por defecto (dry-run): NO toca la BD, solo informa qué haría.
- El marcador solo se rellena si el Match aún NO tiene marcador (no pisa ediciones manuales).
- Nunca borra partidos.
- Deduplica rival con `resolve_or_create_team` y el Match por (season + equipo + fecha).
"""

from datetime import datetime

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from .models import Match, Team, resolve_or_create_team


def _parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_date(raw):
    value = str(raw or "").strip()
    if "T" in value:
        value = value.split("T", 1)[0].strip()
    if " " in value:
        value = value.split(" ", 1)[0].strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _team_keys(name):
    try:
        from .next_match_services import expand_team_lookup_variants

        return set(expand_team_lookup_variants(name))
    except Exception:
        key = slugify(str(name or ""))
        return {key} if key else set()


def _enumerate_round_ids(first_payload, *, max_rounds):
    rounds = []
    cur = str(first_payload.get("jornada") or "").strip()
    if cur:
        rounds.append(cur)
    for bucket in first_payload.get("listado_jornadas") or []:
        if not isinstance(bucket, dict):
            continue
        for row in bucket.get("jornadas") or []:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("codjornada") or row.get("codigo") or "").strip()
            if rid and rid not in rounds:
                rounds.append(rid)
    numeric = [rid for rid in rounds if str(rid).isdigit()]
    if numeric:
        rounds = sorted({rid for rid in numeric}, key=lambda v: int(v))
    return rounds[:max_rounds]


def sync_team_calendar_from_universo(primary_team, *, write=False, max_rounds=40, fetch_results=None):
    """Devuelve un resumen {created, updated, skipped, errors, rows[]}.

    `fetch_results(group_key, round_id) -> dict` se inyecta para test; por defecto usa el cliente
    real de Universo.
    """
    summary = {"created": 0, "updated": 0, "skipped": 0, "errors": [], "rows": [], "write": bool(write)}
    if not primary_team:
        summary["errors"].append("Equipo no válido.")
        return summary
    group = getattr(primary_team, "group", None)
    season = getattr(group, "season", None) if group else None
    group_key = str(getattr(group, "external_id", "") or "").strip() if group else ""
    if not group or not season or not group_key:
        summary["errors"].append(
            "El equipo no tiene grupo/temporada con ID externo de Universo (Group.external_id). "
            "Vincula la competición primero."
        )
        return summary

    if fetch_results is None:
        from .universo_client import fetch_universo_live_results as fetch_results  # noqa: WPS433

    team_code = str(getattr(primary_team, "external_id", "") or "").strip()
    team_keys = _team_keys(getattr(primary_team, "name", ""))

    try:
        first = fetch_results(group_key, "") or {}
    except Exception as exc:
        summary["errors"].append(f"No se pudo consultar Universo: {exc.__class__.__name__}")
        return summary
    round_ids = _enumerate_round_ids(first, max_rounds=max_rounds) or [str(first.get("jornada") or "").strip()]

    today = timezone.localdate()
    seen_dates = set()
    for rid in round_ids:
        try:
            payload = first if (rid and rid == str(first.get("jornada") or "").strip()) else (fetch_results(group_key, rid) or {})
        except Exception:
            continue
        fallback_round = str(payload.get("nombre_jornada") or payload.get("jornada") or rid).strip()
        for row in payload.get("partidos") or []:
            if not isinstance(row, dict):
                continue
            home_name = str(row.get("Nombre_equipo_local") or "").strip()
            away_name = str(row.get("Nombre_equipo_visitante") or "").strip()
            home_code = str(row.get("CodEquipo_local") or "").strip()
            away_code = str(row.get("CodEquipo_visitante") or "").strip()
            is_home = None
            opponent_name = ""
            if team_code and team_code == home_code:
                is_home, opponent_name = True, away_name
            elif team_code and team_code == away_code:
                is_home, opponent_name = False, home_name
            else:
                if team_keys & _team_keys(home_name):
                    is_home, opponent_name = True, away_name
                elif team_keys & _team_keys(away_name):
                    is_home, opponent_name = False, home_name
            if is_home is None or not opponent_name:
                continue  # no involucra a nuestro equipo
            match_date = _parse_date(row.get("fecha"))
            if not match_date:
                continue
            if match_date in seen_dates:
                continue
            seen_dates.add(match_date)

            gh, ga = _parse_int(row.get("Goles_casa")), _parse_int(row.get("Goles_visitante"))
            has_score = gh is not None and ga is not None
            score_for = (gh if is_home else ga) if has_score else None
            score_against = (ga if is_home else gh) if has_score else None
            round_label = str(row.get("nombre_jornada") or row.get("jornada") or fallback_round or "").strip()

            existing = (
                Match.objects.filter(season=season)
                .filter(Q(home_team=primary_team) | Q(away_team=primary_team))
                .filter(date=match_date)
                .order_by("-id")
                .first()
            )
            action, detail = _apply_row(
                primary_team=primary_team,
                group=group,
                season=season,
                existing=existing,
                opponent_name=opponent_name,
                is_home=is_home,
                match_date=match_date,
                round_label=round_label,
                score_for=score_for,
                score_against=score_against,
                write=write,
            )
            summary[action] += 1
            summary["rows"].append(
                {
                    "date": match_date.isoformat(),
                    "opponent": opponent_name,
                    "home": is_home,
                    "score": (f"{score_for}-{score_against}" if has_score else ""),
                    "round": round_label,
                    "action": action,
                    "detail": detail,
                    "past": match_date < today,
                }
            )
    summary["rows"].sort(key=lambda r: r["date"])
    return summary


def _resolve_opponent(primary_team, group, opponent_name, *, write):
    opp = (
        Team.objects.filter(group=group)
        .filter(
            Q(name__iexact=opponent_name)
            | Q(short_name__iexact=opponent_name)
            | Q(slug__iexact=slugify(opponent_name))
        )
        .order_by("-is_primary", "name")
        .first()
    ) or (
        Team.objects.filter(
            Q(name__iexact=opponent_name)
            | Q(short_name__iexact=opponent_name)
            | Q(slug__iexact=slugify(opponent_name))
        )
        .order_by("-is_primary", "name")
        .first()
    )
    if opp:
        return opp
    if not write:
        return None  # en dry-run no creamos equipos
    opp, _ = resolve_or_create_team(name=opponent_name, group=group, defaults={"short_name": opponent_name[:60]})
    return opp


def _apply_row(*, primary_team, group, season, existing, opponent_name, is_home, match_date, round_label, score_for, score_against, write):
    opponent = _resolve_opponent(primary_team, group, opponent_name, write=write)
    home_team = primary_team if is_home else opponent
    away_team = opponent if is_home else primary_team
    # Marcador en orientación local/visitante:
    home_score = (score_for if is_home else score_against)
    away_score = (score_against if is_home else score_for)

    if not existing:
        if not write:
            return "created", "se crearía"
        Match.objects.create(
            season=season,
            group=group,
            round=round_label,
            date=match_date,
            home_team=home_team,
            away_team=away_team,
            context=Match.CONTEXT_LEAGUE,
            home_score=home_score,
            away_score=away_score,
        )
        return "created", "creado"

    # Ya existe: actualizamos con cuidado (no pisar marcador manual).
    changes = []
    update_fields = []
    if round_label and existing.round != round_label:
        existing.round = round_label
        update_fields.append("round")
        changes.append("jornada")
    if opponent is not None:
        if existing.home_team_id != getattr(home_team, "id", None):
            existing.home_team = home_team
            update_fields.append("home_team")
            changes.append("local")
        if existing.away_team_id != getattr(away_team, "id", None):
            existing.away_team = away_team
            update_fields.append("away_team")
            changes.append("visitante")
    # Marcador: SOLO si el partido no tiene ya uno (no pisar ediciones del cuerpo técnico).
    if home_score is not None and away_score is not None and existing.home_score is None and existing.away_score is None:
        existing.home_score = home_score
        existing.away_score = away_score
        update_fields.extend(["home_score", "away_score"])
        changes.append("resultado")
    if not update_fields:
        return "skipped", "sin cambios"
    if not write:
        return "updated", "se actualizaría (" + ", ".join(changes) + ")"
    existing.save(update_fields=sorted(set(update_fields)))
    return "updated", "actualizado (" + ", ".join(changes) + ")"
