"""Quita el lienzo duplicado que la copia "versión original" dejó dentro de las tareas.

`_ensure_original_task_snapshot` guardaba en `meta.original_version` una copia entera del lienzo
(`graphic_editor`), incluso cuando el guardado solo cambiaba TEXTOS de la ficha. En una tarea real
el lienzo son ~2 MB, así que el primer guardado engordaba la fila un 50% de una vez y para siempre.

Este comando solo borra la copia cuando es REDUNDANTE: cuando el lienzo copiado es idéntico, byte
a byte, al lienzo que la tarea tiene ahora. En ese caso restaurar la versión original devolvería
exactamente el dibujo que ya está puesto, así que quitarla no pierde nada. Si el usuario cambió el
dibujo de verdad, los dos lienzos difieren y la copia se respeta.

Uso:
    python3 manage.py prune_original_version_canvas            # solo informa
    python3 manage.py prune_original_version_canvas --apply    # escribe
    python3 manage.py prune_original_version_canvas --apply --task 646
"""
import json

from django.core.management.base import BaseCommand

from football.models import SessionTask


def _kb(value):
    try:
        return len(json.dumps(value, separators=(",", ":"), default=str)) / 1024.0
    except Exception:
        return 0.0


def _canon(value):
    """Serialización estable, para comparar dos lienzos sin que importe el orden de las claves."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return None


class Command(BaseCommand):
    help = "Quita el lienzo duplicado dentro de meta.original_version cuando es idéntico al actual."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios (por defecto solo informa).")
        parser.add_argument("--task", type=int, default=0, help="Limitar a una tarea concreta.")

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        only_task = int(options.get("task") or 0)

        qs = SessionTask.objects.filter(deleted_at__isnull=True)
        if only_task:
            qs = qs.filter(id=only_task)

        revisadas = 0
        podadas = 0
        respetadas = 0
        kb_liberados = 0.0

        for task in qs.iterator():
            layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
            meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
            original = meta.get("original_version") if isinstance(meta.get("original_version"), dict) else None
            if not original:
                continue
            copia = original.get("graphic_editor")
            if not isinstance(copia, dict) or not copia:
                continue
            revisadas += 1

            actual = meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {}
            if _canon(copia) != _canon(actual) or _canon(copia) is None:
                respetadas += 1
                self.stdout.write(
                    f"  · tarea {task.id} «{str(task.title or '')[:40]}»: el dibujo original DIFIERE del actual, se respeta"
                )
                continue

            ahorro = _kb(copia)
            podadas += 1
            kb_liberados += ahorro
            self.stdout.write(
                f"  ✓ tarea {task.id} «{str(task.title or '')[:40]}»: copia redundante de {ahorro:.1f} KB"
            )
            if not apply_changes:
                continue

            nuevo_layout = dict(layout)
            nuevo_meta = dict(meta)
            nuevo_original = dict(original)
            nuevo_original.pop("graphic_editor", None)
            nuevo_meta["original_version"] = nuevo_original
            nuevo_layout["meta"] = nuevo_meta
            task.tactical_layout = nuevo_layout
            task.save(update_fields=["tactical_layout"])

        self.stdout.write("")
        self.stdout.write(f"tareas con copia del lienzo : {revisadas}")
        self.stdout.write(f"copias redundantes          : {podadas}  ({kb_liberados:.1f} KB)")
        self.stdout.write(f"copias respetadas           : {respetadas}")
        if not apply_changes:
            self.stdout.write(self.style.WARNING("Simulación: nada escrito. Repite con --apply."))
        else:
            self.stdout.write(self.style.SUCCESS("Aplicado."))
