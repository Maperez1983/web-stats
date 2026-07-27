"""Clasificación 2026/2027 (Benagalbón) — tabla LIMPIA a 0 con los 16 equipos nuevos.

Tras el rollover (0190) el equipo ya está en el grupo de División de Honor 2026/2027, pero:
- El snapshot de La Preferente que lee la home seguía con la tabla FINAL 2025/2026.
- Las `TeamStanding` del grupo 2026/2027 estaban con basura de un sync fallido (PJ=59, PTS=0).

Esta migración deja la clasificación 2026/2027 a CERO con los 16 equipos reales del grupo
(la liga aún no tiene calendario), tanto en BD (`TeamStanding`) como en el snapshot que pinta
la home. Cuando la federación publique el calendario y corra un sync real de La Preferente
(IP residencial), se sustituirá por los datos en vivo.

Dirigida, guardada e idempotente: solo actúa si la ficha principal ya está en un grupo cuya
temporada es 2026/2027. En BD frescas no existe → no hace nada.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)

_KEEP_NAME_KEY = "benagalbondivisiondehonor"
_TARGET_SEASON_NEEDLE = "2026/2027"


def _seed_zero(apps, schema_editor):
    from football.models import (
        Team,
        TeamStanding,
        WorkspaceCompetitionSnapshot,
    )

    try:
        keep = (
            Team.objects.filter(is_primary=True, name_key=_KEEP_NAME_KEY)
            .order_by("id")
            .first()
        )
        if keep is None or keep.group is None or getattr(keep.group, "season", None) is None:
            return
        group = keep.group
        season = group.season
        if _TARGET_SEASON_NEEDLE not in (season.name or ""):
            return  # de seguridad: solo cuando el rollover a 2026/2027 ya se aplicó

        teams = list(Team.objects.filter(group=group).order_by("name"))
        if not teams:
            return

        payload = []
        for idx, team in enumerate(teams, start=1):
            TeamStanding.objects.update_or_create(
                season=season,
                group=group,
                team=team,
                defaults=dict(
                    position=idx,
                    played=0,
                    wins=0,
                    draws=0,
                    losses=0,
                    goals_for=0,
                    goals_against=0,
                    goal_difference=0,
                    points=0,
                ),
            )
            name = team.name or ""
            payload.append(
                {
                    "rank": idx,
                    "team": name.upper(),
                    "full_name": name,
                    "team_code": "",
                    "crest_url": "",
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                }
            )

        # Sobrescribe el/los snapshot(s) del equipo (la home lee `standings_payload`).
        snaps = list(WorkspaceCompetitionSnapshot.objects.filter(context__team=keep))
        for snap in snaps:
            snap.standings_payload = payload
            snap.save(update_fields=["standings_payload", "updated_at"])
        logger.info(
            "Clasificación 2026/2027 sembrada a 0: grupo=%s equipos=%s snapshots=%s",
            group.id,
            len(teams),
            len(snaps),
        )
    except Exception:  # pragma: no cover - remediación puntual, no debe romper el deploy
        logger.exception("Seed clasificación 2026/2027 falló (no bloquea el deploy)")


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0190_rollover_benagalbon_2026_27"),
    ]

    operations = [
        migrations.RunPython(_seed_zero, migrations.RunPython.noop),
    ]
