from django.db import migrations


def backfill_physical(apps, schema_editor):
    """Copia los datos FÍSICOS (tests, wellness, RPE/minutos, madurez) que hoy viven enterrados en
    cada PlayerEvaluation a un registro de PlayerPhysicalMetric (fechado por evaluated_on), para que
    el histórico físico aparezca en la pestaña Físico y no se pierda al dejar de recapturarlo en la
    evaluación. Idempotente: marca cada registro con [eval#<id>] y no duplica."""
    PlayerEvaluation = apps.get_model('football', 'PlayerEvaluation')
    PlayerPhysicalMetric = apps.get_model('football', 'PlayerPhysicalMetric')

    phys_fields = [
        'yo_yo_ir1_m', 'sprint_5m_s', 'sprint_10m_s', 'sprint_20m_s', 'agility_505_s', 'cmj_cm',
        'copenhagen_seconds', 'wellness_sleep', 'wellness_fatigue', 'wellness_soreness',
        'wellness_stress', 'wellness_motivation', 'session_rpe', 'session_minutes',
        'maturation_status', 'maturity_offset_years', 'growth_velocity_cm_year',
    ]

    for ev in PlayerEvaluation.objects.all().iterator():
        if not any(getattr(ev, f, None) not in (None, '') for f in phys_fields):
            continue
        marker = f"[eval#{ev.pk}]"
        if PlayerPhysicalMetric.objects.filter(player_id=ev.player_id, notes__contains=marker).exists():
            continue
        PlayerPhysicalMetric.objects.create(
            player_id=ev.player_id,
            recorded_on=ev.evaluated_on,
            rpe=ev.session_rpe,
            session_minutes=ev.session_minutes,
            wellness_sleep=ev.wellness_sleep,
            wellness_fatigue=ev.wellness_fatigue,
            wellness_soreness=ev.wellness_soreness,
            wellness_stress=ev.wellness_stress,
            wellness_motivation=ev.wellness_motivation,
            yo_yo_ir1_m=ev.yo_yo_ir1_m,
            sprint_5m_s=ev.sprint_5m_s,
            sprint_10m_s=ev.sprint_10m_s,
            sprint_20m_s=ev.sprint_20m_s,
            agility_505_s=ev.agility_505_s,
            cmj_cm=ev.cmj_cm,
            copenhagen_seconds=ev.copenhagen_seconds,
            maturation_status=ev.maturation_status or '',
            maturity_offset_years=ev.maturity_offset_years,
            growth_velocity_cm_year=ev.growth_velocity_cm_year,
            notes=f"Importado de la evaluación del {ev.evaluated_on} {marker}",
        )


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0176_playerphysicalmetric_agility_505_s_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_physical, migrations.RunPython.noop),
    ]
