"""
Junta en UNO todos los microciclos de la biblioteca de tareas y libera las semanas del calendario.

El código antiguo creaba la biblioteca con get_or_create por (equipo, semana en curso), así que
aparecía una nueva cada semana que se abría la biblioteca. En producción había 13, con 11 ocupando
semanas reales. Como `TrainingMicrocycle` tiene unique(team, week_start), cada una de esas semanas
quedaba bloqueada: al programar una sesión de esos días no se podía crear su microciclo real y la
sesión terminaba fuera de los listados.

La 0221 sacó una del calendario. Esta consolida el resto: mueve sus sesiones al microciclo de la
semana centinela y borra los contenedores que quedan vacíos.

Por qué se puede hacer sin perder nada: la semana de un microciclo de biblioteca no significa nada
(es un contenedor técnico), y las tareas cuelgan de la SESIÓN, no del microciclo, así que al mover
la sesión se mueve todo con ella.

Cuidados:
- Se BORRA solo lo que queda a cero. Borrar un microciclo arrastra sus sesiones en cascada, así que
  se cuenta otra vez antes de borrar y, si queda alguna, no se toca.
- No se tocan las semanas centinela de otras cosas: la bandeja de sueltas (2000-01-01), la papelera
  (1970-01-01) ni la biblioteca de PLANTILLAS DE SESIÓN (2000-01-03), que es otra cosa y también
  empieza por "Biblioteca".
- `TrainingSession` tiene unique(microciclo, fecha, nombre en minúsculas). Al juntarlas todas en
  uno podrían chocar; se comprueba antes de mover y, si chocara, se deja donde está en vez de
  reventar la migración o pisar datos.
"""
from datetime import date

from django.db import migrations

SENTINEL_START = date(2000, 1, 10)
SENTINEL_END = date(2000, 1, 16)
MARKER = '[2J_LIBRARY_MICROCYCLE]'
# Semanas centinela que pertenecen a OTRA cosa: no se tocan.
RESERVED_STARTS = {date(2000, 1, 1), date(2000, 1, 3), date(1970, 1, 1)}


def _is_task_library(microcycle):
    if microcycle.week_start in RESERVED_STARTS:
        return False
    notes = str(getattr(microcycle, 'notes', '') or '')
    if MARKER in notes:
        return True
    title = str(getattr(microcycle, 'title', '') or '')
    return title.strip().lower().startswith('biblioteca ')


def consolidate(apps, schema_editor):
    TrainingMicrocycle = apps.get_model('football', 'TrainingMicrocycle')
    TrainingSession = apps.get_model('football', 'TrainingSession')

    team_ids = list(TrainingMicrocycle.objects.values_list('team_id', flat=True).distinct())
    for team_id in team_ids:
        libraries = [
            mc
            for mc in TrainingMicrocycle.objects.filter(team_id=team_id).order_by('week_start', 'id')
            if _is_task_library(mc)
        ]
        if len(libraries) < 2:
            continue

        # Destino: el que ya esté en la semana centinela; si no hay, el más antiguo se muda allí.
        target = next((mc for mc in libraries if mc.week_start == SENTINEL_START), None)
        if target is None:
            target = libraries[0]
            target.week_start = SENTINEL_START
            target.week_end = SENTINEL_END
            target.save(update_fields=['week_start', 'week_end'])

        # Nombres ya ocupados en el destino, para respetar unique(microciclo, fecha, nombre).
        taken = {
            (s.session_date, str(s.focus or '').strip().lower())
            for s in TrainingSession.objects.filter(microcycle=target)
        }

        for mc in libraries:
            if mc.id == target.id:
                continue
            for session in TrainingSession.objects.filter(microcycle=mc):
                key = (session.session_date, str(session.focus or '').strip().lower())
                if key in taken:
                    # Chocaría con una que ya está en el destino: se queda donde está. Mejor una
                    # semana bloqueada de más que perder o pisar una sesión con sus tareas.
                    continue
                session.microcycle = target
                session.save(update_fields=['microcycle'])
                taken.add(key)

            # Solo se borra lo que queda VACÍO: el borrado arrastra sesiones en cascada.
            if not TrainingSession.objects.filter(microcycle=mc).exists():
                mc.delete()


def back(apps, schema_editor):
    # No se deshace: repartir otra vez las sesiones por semanas inventadas no reconstruye nada.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0221_biblioteca_tareas_semana_centinela'),
    ]

    operations = [
        migrations.RunPython(consolidate, back),
    ]
