"""
Saca el microciclo de la BIBLIOTECA DE TAREAS del calendario real.

Se creaba en la semana en curso, y como `TrainingMicrocycle` tiene unique(team, week_start), esa
semana quedaba OCUPADA: al programar una sesión de esos días no se podía crear su microciclo real,
y la sesión acababa dentro del microciclo de biblioteca. Como las sesiones de biblioteca se
excluyen en todas partes (planificador, informe, carga), la sesión desaparecía de la vista.

Es el mismo destrozo que reparó la migración 0214 para las plantillas de sesión; aquí se cierra
para las tareas. El microciclo de biblioteca es un contenedor técnico: su semana no significa
nada, así que moverlo no pierde información.

Solo se mueven los que son biblioteca de verdad (marcador en notas o título "Biblioteca ...") y
que hoy ocupan una semana del calendario. Si un equipo tuviera más de uno, el primero va a la
semana centinela y los demás se dejan como están para no chocar con el unique: se anota en las
notas para poder revisarlos a mano.
"""
from datetime import date

from django.db import migrations

SENTINEL_START = date(2000, 1, 10)
SENTINEL_END = date(2000, 1, 16)
MARKER = '[2J_LIBRARY_MICROCYCLE]'
# Semanas que ya son centinela de otra cosa (bandeja de sueltas, papelera, plantillas de sesión).
RESERVED_STARTS = {date(2000, 1, 1), date(2000, 1, 3), date(1970, 1, 1)}


def _is_library(microcycle):
    notes = str(getattr(microcycle, 'notes', '') or '')
    if MARKER in notes:
        return True
    title = str(getattr(microcycle, 'title', '') or '')
    return title.strip().lower().startswith('biblioteca ')


def move_task_library_out_of_calendar(apps, schema_editor):
    TrainingMicrocycle = apps.get_model('football', 'TrainingMicrocycle')
    moved = 0
    for team_id in (
        TrainingMicrocycle.objects.values_list('team_id', flat=True).distinct()
    ):
        already = TrainingMicrocycle.objects.filter(team_id=team_id, week_start=SENTINEL_START).exists()
        if already:
            continue
        candidates = [
            mc
            for mc in TrainingMicrocycle.objects.filter(team_id=team_id).order_by('week_start', 'id')
            if _is_library(mc) and mc.week_start not in RESERVED_STARTS
        ]
        if not candidates:
            continue
        target = candidates[0]
        target.week_start = SENTINEL_START
        target.week_end = SENTINEL_END
        target.save(update_fields=['week_start', 'week_end'])
        moved += 1
        for extra in candidates[1:]:
            notes = str(extra.notes or '')
            flag = '(Sistema) Duplicado de biblioteca: revisar y unificar.'
            if flag not in notes:
                extra.notes = (notes + '\n' if notes else '') + flag
                extra.save(update_fields=['notes'])


def back(apps, schema_editor):
    # No se deshace: devolverlo a "la semana en curso" no tiene sentido (esa semana ya no es la
    # misma) y volvería a ocupar un hueco real del calendario.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0220_valoracion_autor'),
    ]

    operations = [
        migrations.RunPython(move_task_library_out_of_calendar, back),
    ]
