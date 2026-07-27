"""Cambio de temporada 2026/2027 (Benagalbón) — lado competición federativa.

Consolida las 3 fichas de equipo del mismo club en la PRINCIPAL y repunta su grupo a
la División de Honor 2026/2027, que es exactamente lo que hace el rollover automático de
Universo (`universo_group_services`): `Team.group = <grupo temporada nueva>`. Los partidos
y estadísticas de 2025/2026 conservan su propia FK `season`/`club_season`, así que NO se
mueven: el histórico queda intacto en la temporada anterior.

Dirigida, guardada e idempotente:
- Solo actúa sobre la ficha principal (`is_primary=True`, name_key='benagalbondivisiondehonor').
- Fusiona en ella sus duplicados (name_key 'benagalboncd' / 'cdbenagalbon') con
  `merge_teams(keep=principal, drop=dup)` — reasigna clasificación/partidos/memberships del
  duplicado a la principal y borra el duplicado (IRREVERSIBLE; por eso va dirigido por name_key).
- Repunta el grupo al de la MISMA competición cuya temporada sea 2026/2027.
- Si la principal ya está en el grupo 2026/2027, no hace nada (idempotente).
- Cualquier error se registra pero NO bloquea el deploy.

En bases de datos frescas (CI/local) no existen esas fichas → la migración no hace nada.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)

_KEEP_NAME_KEY = "benagalbondivisiondehonor"
_DUP_NAME_KEYS = ("benagalboncd", "cdbenagalbon")
_TARGET_SEASON_NEEDLE = "2026/2027"


def _rollover(apps, schema_editor):
    # merge_teams necesita instancias del modelo VIVO (usa `_meta.related_objects`).
    from football.models import Team, Group, merge_teams

    try:
        keep = (
            Team.objects.filter(is_primary=True, name_key=_KEEP_NAME_KEY)
            .order_by("id")
            .first()
        )
        if keep is None:
            return
        current_group = keep.group
        if current_group is None or getattr(current_group, "season", None) is None:
            return
        competition_id = current_group.season.competition_id

        target = (
            Group.objects.filter(
                season__competition_id=competition_id,
                season__name__icontains=_TARGET_SEASON_NEEDLE,
            )
            .order_by("-id")
            .first()
        )
        if target is None or target.id == current_group.id:
            return

        # Idempotencia: si ya está en el grupo 2026/2027, nada que hacer.
        if keep.group_id == target.id:
            return

        # 1) Fusionar duplicados del mismo club en la ficha principal.
        for dup in (
            Team.objects.filter(name_key__in=_DUP_NAME_KEYS).exclude(pk=keep.pk)
        ):
            merge_teams(keep, dup)
        keep.refresh_from_db()

        # 2) Repuntar la temporada federativa a 2026/2027 (histórico se queda en su season).
        keep.group_id = target.id
        keep.is_primary = True
        keep.save(update_fields=["group", "is_primary"])
        logger.info(
            "Rollover 2026/2027 aplicado: team=%s group %s -> %s",
            keep.id,
            current_group.id,
            target.id,
        )
    except Exception:  # pragma: no cover - remediación puntual, no debe romper el deploy
        logger.exception("Rollover 2026/2027 Benagalbón falló (no bloquea el deploy)")


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0189_alter_player_hairstyle"),
    ]

    operations = [
        migrations.RunPython(_rollover, migrations.RunPython.noop),
    ]
