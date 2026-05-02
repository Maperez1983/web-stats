from django.db import migrations


def remove_system_blueprint_dinamica1(apps, schema_editor):
    Team = apps.get_model('football', 'Team')
    TaskBlueprint = apps.get_model('football', 'TaskBlueprint')

    system_team = Team.objects.filter(slug='pizarra').first()
    if not system_team:
        return

    TaskBlueprint.objects.filter(
        team=system_team,
        name='DINÁMICA 1 · Iniciación (Salida + presión)',
        created_by='system_seed',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0087_system_blueprint_dinamica1'),
    ]

    operations = [
        migrations.RunPython(remove_system_blueprint_dinamica1, reverse_code=migrations.RunPython.noop),
    ]

