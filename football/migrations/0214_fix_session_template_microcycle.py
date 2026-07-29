"""
Repara un efecto secundario de la 1ª versión de "Guardar como plantilla de sesión":
el helper hacía get_or_create del microciclo-biblioteca por la SEMANA EN CURSO, con lo que
agarraba el microciclo REAL de la semana y le añadía el marcador de biblioteca (cambiaba la
numeración de la semana y ensuciaba el microciclo real).

Esta migración:
  1) Quita el marcador de biblioteca de los microciclos REALES mal marcados (los que tienen
     asistencia registrada -> no son biblioteca).
  2) Reubica las plantillas de sesión (is_session_template=True) a un microciclo-biblioteca
     DEDICADO por equipo, en una semana-centinela lejana (año 2000) que no colisiona con
     semanas reales. El helper corregido ya usa esa misma semana-centinela.

Idempotente y defensiva.
"""

from datetime import date

from django.db import migrations

MARKER = "[2J_LIBRARY_MICROCYCLE]"
SENTINEL_START = date(2000, 1, 3)
SENTINEL_END = date(2000, 1, 9)


def forwards(apps, schema_editor):
    TM = apps.get_model("football", "TrainingMicrocycle")
    TS = apps.get_model("football", "TrainingSession")
    TSA = apps.get_model("football", "TrainingSessionAttendance")

    # 1) Desmarcar microciclos reales mal marcados (tienen asistencia => no son biblioteca).
    real_mc_ids = set(
        i for i in TSA.objects.values_list("session__microcycle_id", flat=True) if i
    )
    for mc in TM.objects.filter(notes__icontains=MARKER):
        if mc.id in real_mc_ids:
            try:
                mc.notes = (mc.notes or "").replace(MARKER, "").strip()
                mc.save(update_fields=["notes"])
            except Exception:
                continue

    # 2) Reubicar plantillas a un microciclo-biblioteca dedicado (semana centinela).
    for tpl in TS.objects.filter(is_session_template=True).select_related("microcycle"):
        try:
            team_id = tpl.microcycle.team_id if tpl.microcycle_id else None
            if not team_id:
                continue
            lib, _created = TM.objects.get_or_create(
                team_id=team_id,
                week_start=SENTINEL_START,
                defaults={
                    "week_end": SENTINEL_END,
                    "title": "Biblioteca de sesiones",
                    "objective": "Plantillas de sesión reutilizables",
                    "status": "draft",
                    "notes": MARKER,
                },
            )
            if MARKER not in (lib.notes or ""):
                lib.notes = ((lib.notes + "\n") if lib.notes else "") + MARKER
                lib.save(update_fields=["notes"])
            if tpl.microcycle_id != lib.id:
                tpl.microcycle_id = lib.id
                tpl.session_date = SENTINEL_START
                tpl.save(update_fields=["microcycle", "session_date"])
        except Exception:
            continue


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0213_session_template_flag"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
