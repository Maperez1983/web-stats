# Generated migration

from django.db import migrations, models


def extract_division_from_name(apps, schema_editor):
    """Extrae A/B/C del Team.name si existe (ej. 'Cadete A' → 'A')"""
    Team = apps.get_model('football', 'Team')
    for team in Team.objects.all():
        name = str(team.name or '').strip()
        # Buscar última letra mayúscula al final: "Cadete A" → "A"
        if name and name[-1].isupper() and name[-1].isalpha():
            team.division = name[-1]
            team.save(update_fields=['division'])


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0239_video_atado_al_partido'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='division',
            field=models.CharField(
                max_length=4,
                blank=True,
                null=True,
                help_text='División del equipo dentro de la categoría (A, B, C, etc.)'
            ),
        ),
        migrations.RunPython(extract_division_from_name),
    ]
