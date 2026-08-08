"""Rehace la copia ligera de las tareas que dicen no tener dibujo teniéndolo.

`task_layout_light` es la copia del layout SIN el lienzo, y de ahí salen los listados: si dice
`has_canvas: false` cuando el lienzo tiene 27 objetos, la tarea aparece como vacía en todas
partes. Pasó de verdad: 13 tareas con nombre, objetivo y dibujo -"Partido condicionado",
"Transiciones", "Basculación y pase filtrado"- salieron en el recuento como "no tienen nada",
y estuvieron a un paso de acabar en la papelera por eso.

La copia se rehace con `build_layout_light`, que es el ÚNICO productor legítimo (lo usan el
guardado y el comando de relleno), así que no puede quedar distinta de la que haría la app.

    python3 manage.py arreglar_copia_ligera            # sólo propone
    python3 manage.py arreglar_copia_ligera --apply
"""
from django.core.management.base import BaseCommand

from football.library_repositories import is_library_session
from football.models import SessionTask
from football.task_script import build_layout_light


def objetos_del_lienzo(tarea):
    layout = tarea.tactical_layout if isinstance(tarea.tactical_layout, dict) else {}
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    graphic = meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {}
    estado = graphic.get("canvas_state") if isinstance(graphic.get("canvas_state"), dict) else {}
    objetos = estado.get("objects") if isinstance(estado.get("objects"), list) else []
    return len(objetos)


class Command(BaseCommand):
    help = "Rehace task_layout_light donde dice que no hay dibujo y sí lo hay. No borra nada."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe (por defecto sólo propone).")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")

    def handle(self, *args, **options):
        aplicar = bool(options.get("apply"))
        equipo = int(options.get("team") or 0)

        qs = SessionTask.objects.select_related("session__microcycle__team").filter(deleted_at__isnull=True)
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        desfasadas = []
        for tarea in qs.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            light = tarea.task_layout_light if isinstance(tarea.task_layout_light, dict) else {}
            if light.get("has_canvas"):
                continue
            objetos = objetos_del_lienzo(tarea)
            if objetos:
                desfasadas.append((tarea, objetos))

        self.stdout.write(self.style.SUCCESS(
            f"\nDicen no tener dibujo y lo tienen: {len(desfasadas)}"
        ))
        for tarea, objetos in desfasadas[:40]:
            self.stdout.write(f'  {tarea.id:>6}  {objetos:>3} objetos  {str(tarea.title or "")[:50]}')
        if len(desfasadas) > 40:
            self.stdout.write(f"  … y {len(desfasadas) - 40} más")

        if not aplicar:
            self.stdout.write(self.style.WARNING("\nPropuesta: nada escrito. Repite con --apply."))
            return

        escritas = 0
        for tarea, _ in desfasadas:
            nueva = build_layout_light(tarea.tactical_layout)
            if not isinstance(nueva, dict) or not nueva.get("has_canvas"):
                self.stdout.write(self.style.WARNING(
                    f"  {tarea.id}: la copia rehecha sigue diciendo que no hay dibujo; se deja como está"
                ))
                continue
            # update() y no save(): save() vuelve a derivar task_family del JSON y las tareas
            # catalogadas a mano llevan el tipo en la COLUMNA, no en el JSON.
            SessionTask.objects.filter(id=tarea.id).update(task_layout_light=nueva)
            escritas += 1

        self.stdout.write(self.style.SUCCESS(f"\nAplicado: {escritas} copias ligeras al día."))
