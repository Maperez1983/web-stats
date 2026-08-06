"""Team.division: la letra del equipo dentro de su categoria (Cadete A / Cadete B).

Venia de la rama fix/coleccion-carpeta como 0240, pero main ya tiene una 0240 propia y ha
llegado hasta la 0247, asi que se renumera detras.

El paso de datos se ha estrechado. El original tomaba la ULTIMA LETRA MAYUSCULA del nombre:
con "Mijas Las Lagunas B" acierta, pero con un nombre en mayusculas -que es como estan casi
todos los rivales importados- le pone division a cualquiera: "PIZARRA" se quedaba en "A" y
"MARACENA" en "A". Ahora se exige que el nombre termine en " X": espacio y UNA sola letra.
"""
from django.db import migrations, models

LETRAS = set("ABCDEFGH")


def division_desde_el_nombre(apps, schema_editor):
    Team = apps.get_model('football', 'Team')
    a_guardar = []
    for team in Team.objects.all().only('id', 'name', 'division'):
        nombre = str(team.name or '').rstrip()
        # " B" al final: espacio + una letra. Sin el espacio, cualquier nombre en mayusculas
        # colaba y se llevaba una division inventada.
        if len(nombre) >= 3 and nombre[-1] in LETRAS and nombre[-2] == ' ':
            if team.division != nombre[-1]:
                team.division = nombre[-1]
                a_guardar.append(team)
    if a_guardar:
        Team.objects.bulk_update(a_guardar, ['division'], batch_size=200)


def deshacer(apps, schema_editor):
    """Vaciar la columna basta: la crea esta misma migracion."""
    apps.get_model('football', 'Team').objects.exclude(division=None).update(division=None)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0247_seasonwatch_seasonwatchnote_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='division',
            field=models.CharField(
                max_length=4,
                blank=True,
                null=True,
                help_text='División del equipo dentro de la categoría (A, B, C, etc.)',
            ),
        ),
        migrations.RunPython(division_desde_el_nombre, deshacer),
    ]
