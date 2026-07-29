"""
Normaliza los ojeados "A prueba (ojeado)" que VIENEN A ENTRENAR
(`ScoutingTarget.available_for_coach_tools=True`, no descartado/fichado) para que
tengan una "Ficha jugador" real y aparezcan en TODAS las listas del entrenador
(sesión, plantilla, informes, home), no solo en la pizarra.

Por cada ojeado a-prueba:
  1. Se asegura un `Player` enlazado (crea uno si falta), re-anclado al equipo
     principal del club, activo y SIN licencia federativa (no cuenta como fichado).
  2. Se crea una membresía de temporada en estado "pendiente" (= "A prueba", no
     confirmado): así la home y la plantilla lo incluyen vía la lógica existente,
     y la convocatoria oficial (solo confirmados) lo sigue excluyendo.

Idempotente y defensiva por fila (un ojeado con datos raros no rompe el resto).
"""

from django.db import migrations


def forwards(apps, schema_editor):
    ScoutingTarget = apps.get_model("football", "ScoutingTarget")
    Player = apps.get_model("football", "Player")
    WorkspaceSeason = apps.get_model("football", "WorkspaceSeason")
    WorkspaceSeasonPlayer = apps.get_model("football", "WorkspaceSeasonPlayer")

    # Estados terminales que NO son "a prueba" (ya fichados o descartados).
    TERMINAL = {"discarded", "signed", "signed_other"}

    qs = (
        ScoutingTarget.objects.filter(available_for_coach_tools=True)
        .exclude(status__in=TERMINAL)
        .select_related("workspace", "player")
    )
    for tgt in qs.iterator():
        try:
            ws = tgt.workspace
            if ws is None:
                continue
            team = getattr(ws, "primary_team", None)
            if team is None:
                continue
            name = (tgt.subject_name or "").strip()
            if not name:
                continue

            player = tgt.player
            if player is None:
                player, _created = Player.objects.get_or_create(
                    team=team,
                    name=name,
                    defaults={
                        "full_name": name,
                        "origin_team": tgt.subject_team_name or "",
                        "position": tgt.position or "",
                        "dominant_foot": tgt.dominant_foot or "",
                        "birth_date": tgt.birth_date,
                        "is_active": True,
                        "has_federative_license": False,
                    },
                )
                tgt.player = player
                tgt.save(update_fields=["player", "updated_at"])
            else:
                changed_fields = []
                if getattr(player, "team_id", None) != team.id:
                    player.team = team
                    changed_fields.append("team")
                if not getattr(player, "is_active", True):
                    player.is_active = True
                    changed_fields.append("is_active")
                if changed_fields:
                    player.save(update_fields=changed_fields)

            # Membresía de temporada "pendiente" (= A prueba) en la temporada activa.
            season = (
                WorkspaceSeason.objects.filter(workspace=ws, is_active=True)
                .order_by("-start_date", "-id")
                .first()
            )
            if season is not None:
                WorkspaceSeasonPlayer.objects.get_or_create(
                    season=season,
                    player=player,
                    defaults={
                        "team": team,
                        "status": "pending",
                        "is_confirmed": False,
                    },
                )
        except Exception:
            # Nunca abortar el deploy por un ojeado con datos inconsistentes.
            continue


def backwards(apps, schema_editor):
    # No se revierte automáticamente: borrar jugadores/membresías creados sería
    # peligroso (podrían tener datos añadidos después). Descartar el ojeado ya
    # desactiva su ficha por la lógica de la app.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0208_discharge_stuck_injuries"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
