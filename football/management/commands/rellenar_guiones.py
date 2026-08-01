"""
Rellena la copia ligera (y con ella el GUION) de las tareas que ya existían.

El guion se deriva en `SessionTask.save()`, así que solo lo tienen las tareas guardadas desde que
se desplegó. Las anteriores lo tienen vacío y la ficha no puede reproducir su movimiento aunque
la tarea tenga pasos dibujados. Esto lo rellena de una pasada.

Por qué NO llama a `save()`: el guardado del modelo arrastra efectos que aquí no queremos
(mover blobs de portada/preview entre columnas, tocar `cover_present`, disparar señales). Se
escribe solo `task_layout_light` con `queryset.update()`, que es exactamente el dato que falta.
La copia ligera se construye con `task_script.build_layout_light`, el mismo código que usa el
guardado: si divergieran, una tarea rellenada aquí y otra guardada en el editor acabarían con
copias distintas.

Es idempotente y no toca `tactical_layout`: se puede repetir sin miedo.

    python manage.py rellenar_guiones --dry-run
    python manage.py rellenar_guiones
    python manage.py rellenar_guiones --equipo 1
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from football.models import SessionTask
from football.task_script import build_layout_light

LOTE = 200


class Command(BaseCommand):
    help = "Recalcula task_layout_light (incluye el guion) de las tareas existentes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Cuenta lo que cambiaría sin escribir nada.",
        )
        parser.add_argument(
            "--equipo",
            type=int,
            default=None,
            help="Limita a las tareas de un equipo (por id).",
        )

    def handle(self, *args, **options):
        seco = bool(options.get("dry_run"))
        equipo = options.get("equipo")

        qs = SessionTask.objects.all().order_by("id")
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        total = qs.count()
        self.stdout.write(f"Tareas a revisar: {total}{' (equipo %s)' % equipo if equipo else ''}")

        revisadas = actualizadas = con_guion = sin_cambio = 0
        pasos_totales = 0
        ids = list(qs.values_list("id", flat=True))

        for inicio in range(0, len(ids), LOTE):
            lote = ids[inicio : inicio + LOTE]
            # `tactical_layout` es la columna pesada y va diferida: aquí SÍ hace falta, pero solo
            # de 200 en 200 para no cargar 18 MB de golpe en memoria.
            for task in SessionTask.objects.filter(id__in=lote).only("id", "tactical_layout", "task_layout_light"):
                revisadas += 1
                nuevo = build_layout_light(task.tactical_layout)
                script = nuevo.get("script") if isinstance(nuevo, dict) else None
                if script:
                    con_guion += 1
                    pasos_totales += len(script.get("steps") or [])
                actual = task.task_layout_light if isinstance(task.task_layout_light, dict) else {}
                if actual == nuevo:
                    sin_cambio += 1
                    continue
                actualizadas += 1
                if not seco:
                    with transaction.atomic():
                        SessionTask.objects.filter(id=task.id).update(task_layout_light=nuevo)

            self.stdout.write(f"  ... {revisadas}/{total}")

        self.stdout.write("")
        self.stdout.write(f"Revisadas:      {revisadas}")
        self.stdout.write(f"Ya correctas:   {sin_cambio}")
        self.stdout.write(f"{'Cambiarían' if seco else 'Actualizadas'}:   {actualizadas}")
        self.stdout.write(f"Con guion:      {con_guion} ({pasos_totales} pasos en total)")
        if seco:
            self.stdout.write(self.style.WARNING("Simulación: no se ha escrito nada."))
        else:
            self.stdout.write(self.style.SUCCESS("Hecho."))
