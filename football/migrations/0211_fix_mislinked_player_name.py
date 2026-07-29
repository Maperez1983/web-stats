"""
Corrección puntual de dato: el ojeado "Ismael Ouatte" (Benagalbón) quedó enlazado
a una ficha de jugador cuyo nombre visible (`name`) era "Ismael Lobato" (misma
persona, mal escrito). El formulario de la ficha solo edita `full_name`, no `name`,
así que se corrige aquí.

Acotada por pk + nombre actual → no-op si ya está corregido o si en otro entorno
ese pk no coincide. Idempotente y segura.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Player = apps.get_model("football", "Player")
    try:
        Player.objects.filter(pk=100, name="Ismael Lobato").update(
            name="Ismael Ouatte", full_name="Ismael Ouatte"
        )
    except Exception:
        pass


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0210_merge_0209_leaves"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
