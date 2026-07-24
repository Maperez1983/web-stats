"""Vuelca las estadísticas por temporada de La Preferente en ExternalSeasonStat.

Recorre la página de equipo por temporada de cada club (según preferente_url),
parsea la plantilla, empareja por nombre con las fichas Player y hace upsert.
Pensado para lanzarse por cron (temporada actual) o a mano (--seasons all)."""
from __future__ import annotations

import datetime as _dt

from django.core.management.base import BaseCommand

from football.models import ExternalSeasonStat, Player, Team
from football.preferente_player_stats import (
    parse_preferente_squad, team_code_from_url, season_team_url, _match_player, _norm,
)
from football.services import _fetch_preferente_response

SRC = ExternalSeasonStat.SOURCE_PREFERENTE


def _current_season_label(today=None):
    d = today or _dt.date.today()
    return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


def _season_range(current, back=8):
    y = int(current.split("/")[0])
    return [f"{y - i}/{y - i + 1}" for i in range(back + 1)]


def _slug_from_url(url):
    parts = [p for p in str(url or "").rstrip("/").split("/") if p]
    return parts[-1] if parts else "equipo"


class Command(BaseCommand):
    help = "Sincroniza estadísticas por temporada de La Preferente (ExternalSeasonStat)."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Solo este equipo (id).")
        parser.add_argument("--seasons", default="current", help="'current', 'all', o '2025/2026,2024/2025'.")
        parser.add_argument("--timeout", type=int, default=25)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opt):
        cur = _current_season_label()
        raw = str(opt["seasons"]).strip().lower()
        if raw == "current":
            seasons = [cur]
        elif raw == "all":
            seasons = _season_range(cur, back=8)
        elif raw == "auto":
            # actual siempre + cualquier temporada del rango que aún no tenga datos.
            seasons = [cur]
            for lb in _season_range(cur, back=8):
                if lb == cur:
                    continue
                if not ExternalSeasonStat.objects.filter(
                    player__isnull=False, source=SRC, season_label=lb,
                    player__team__preferente_url__gt="",
                ).exists():
                    seasons.append(lb)
        else:
            seasons = [s.strip() for s in opt["seasons"].split(",") if s.strip()]

        teams = Team.objects.filter(preferente_url__gt="")
        if opt["team_id"]:
            teams = teams.filter(id=opt["team_id"])
        teams = list(teams)
        if not teams:
            self.stdout.write("Sin equipos con preferente_url.")
            return

        total_up = total_unmatched = 0
        for team in teams:
            code = team_code_from_url(team.preferente_url)
            if not code:
                self.stderr.write(f"[{team}] preferente_url sin código E: {team.preferente_url!r}")
                continue
            slug = _slug_from_url(team.preferente_url)
            players = list(team.players.all())
            for label in seasons:
                url = season_team_url(code, label, slug)
                try:
                    resp = _fetch_preferente_response(url, timeout=opt["timeout"])
                    resp.raise_for_status()
                    html = resp.content.decode("iso-8859-1", "replace")
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(f"[{team} {label}] fetch error: {exc}")
                    continue
                rows = parse_preferente_squad(html)
                for r in rows:
                    matched = _match_player(r["external_name"], players)
                    defaults = {
                        "team_name": team.name,
                        "external_name": r["external_name"],
                        "position": r["position"],
                        "matches": r["matches"],
                        "starts": r["starts"],
                        "minutes": r["minutes"],
                        "goals": r["goals"],
                        "goals_conceded": r["goals_conceded"],
                        "yellow_cards": r["yellow_cards"],
                        "red_cards": r["red_cards"],
                    }
                    if not matched:
                        total_unmatched += 1
                    if opt["dry_run"]:
                        continue
                    if matched:
                        obj = ExternalSeasonStat.objects.filter(player=matched, source=SRC, season_label=label).first()
                    else:
                        obj = ExternalSeasonStat.objects.filter(
                            player__isnull=True, scouting_target__isnull=True, source=SRC,
                            season_label=label, external_name=r["external_name"],
                        ).first()
                    if obj:
                        for k, v in defaults.items():
                            setattr(obj, k, v)
                        obj.save()
                    else:
                        ExternalSeasonStat.objects.create(player=matched, source=SRC, season_label=label, **defaults)
                    total_up += 1
                self.stdout.write(f"[{team} {label}] {len(rows)} jugadores parseados.")
        self.stdout.write(self.style.SUCCESS(
            f"Hecho. Upserts: {total_up} · Sin emparejar: {total_unmatched}"
            + (" (dry-run)" if opt["dry_run"] else "")
        ))
