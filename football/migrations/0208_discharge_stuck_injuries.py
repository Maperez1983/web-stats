from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def discharge_stuck_injuries(apps, schema_editor):
    """Normaliza lesiones ATASCADAS como activas cuando en realidad ya no lo estan.

    Bug corregido: la accion "marcar como alta" ponia is_active=False, pero el save() del modelo lo
    RECALCULABA desde return_date (is_active = return_date > hoy). Con fecha de alta FUTURA volvia a
    is_active=True -> el jugador seguia saliendo lesionado. Ademas is_active es un campo almacenado
    que no se recalcula solo al pasar el tiempo. Aqui damos de alta (recuperado) los registros que:
      - estan marcados como recuperados pero siguen activos (contradiccion), o
      - tienen una fecha de alta (return_date) que ya se cumplio (return_date <= hoy).
    NO se tocan los que tienen fecha de alta futura (return_date > hoy): esos siguen legitimamente
    activos hasta esa fecha; si el usuario quiere darlos de alta ya, usa la accion "alta" (ya
    arreglada, marca is_recovered=True).
    """
    PlayerInjuryRecord = apps.get_model('football', 'PlayerInjuryRecord')
    today = timezone.localdate()
    stuck = PlayerInjuryRecord.objects.filter(is_active=True).filter(
        Q(is_recovered=True) | Q(return_date__isnull=False, return_date__lte=today)
    )
    stuck.update(is_active=False, is_recovered=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0207_backfill_matchevent_kind'),
    ]

    operations = [
        migrations.RunPython(discharge_stuck_injuries, noop),
    ]
