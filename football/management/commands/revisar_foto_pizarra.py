"""¿Por qué a esta tarea no le sale la foto HD de la pizarra? No escribe nada.

Abrir la ficha de una tarea deja apuntado un encargo de foto; `manage.py fotos_pizarra` lo
cumple abriendo el editor de verdad con Playwright. Este comando dice en qué punto está y, si
falló, por qué.

    python3 manage.py revisar_foto_pizarra --ids 711,963,599

DE DÓNDE SALE AHORA LA RESPUESTA (2026-08-08). Antes esto leía `cache`, y en producción eso es
una LocMemCache por proceso con DOS workers de gunicorn: el motivo lo veías o no según el worker
que te contestara, y un reinicio se lo llevaba entero. Por eso una tarea podía quedarse sin foto
y sin una sola pista —le pasó a la 1160—. Ahora el estado vive en la fila `TaskBoardShot`, que es
la misma se pregunte desde donde se pregunte.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from football.models import SessionTask, TaskBoardShot


class Command(BaseCommand):
    help = "Dice por qué falló la foto HD de la pizarra de una tarea. No escribe nada."

    def add_arguments(self, parser):
        parser.add_argument("--ids", default="", help="Lista de ids separados por coma.")

    def handle(self, *args, **options):
        ids = [int(x) for x in str(options.get("ids") or "").replace(" ", "").split(",") if x.isdigit()]
        if not ids:
            self.stdout.write(self.style.WARNING("Dame ids: --ids 711,963"))
            return

        from football import task_board_snapshot as foto

        self.stdout.write("")
        for tid in ids:
            tarea = SessionTask.objects.filter(id=tid).first()
            if not tarea:
                self.stdout.write(f"{tid:>6}  no existe")
                continue
            objetos = foto.board_object_count(tarea)
            limite_ms, reposo_ms = foto._timeouts_for(objetos)
            al_dia = False
            try:
                al_dia = bool(foto.snapshot_is_current(tarea))
            except Exception:
                pass
            shot = TaskBoardShot.objects.filter(task_id=tid).first()

            self.stdout.write(self.style.SUCCESS(f"{tid:>6}  {str(tarea.title or '')[:48]}"))
            self.stdout.write(f"        objetos en la pizarra : {objetos}")
            self.stdout.write(f"        tiempo que se le da   : {limite_ms // 1000}s (+{reposo_ms}ms de reposo)")
            self.stdout.write(f"        foto al día           : {'sí' if al_dia else 'NO'}")
            if shot is None:
                self.stdout.write("        en la cola            : NO hay encargo (abre su ficha una vez)")
            else:
                self.stdout.write(f"        en la cola            : {shot.state} · intento {shot.attempts}/{TaskBoardShot.MAX_INTENTOS}")
                self.stdout.write(f"        la pidió              : {shot.requested_by or '(nadie: sin sesión con la que abrir el editor)'}")
                if shot.leased_until and shot.leased_until > timezone.now():
                    self.stdout.write(f"        haciéndose ahora      : sí, hasta {shot.leased_until:%H:%M:%S}")
                if shot.next_try_at:
                    self.stdout.write(f"        siguiente intento     : {shot.next_try_at:%d/%m %H:%M:%S}")
                self.stdout.write(f"        último motivo         : {shot.last_error or '(ninguno)'}")
            self.stdout.write("")

        self.stdout.write("Este comando no ha escrito nada.")
