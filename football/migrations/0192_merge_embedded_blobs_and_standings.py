from django.db import migrations


class Migration(migrations.Migration):
    """Une las dos 0191 que dependian de 0190 (embedded-blobs de tareas y seed de clasificacion
    2026/27), creadas en paralelo. Sin operaciones: solo resuelve el conflicto de hojas."""

    dependencies = [
        ("football", "0191_seed_benagalbon_2026_27_standings_zero"),
        ("football", "0191_session_task_embedded_blobs"),
    ]

    operations = []
