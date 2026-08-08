"""¿Por qué a esta tarea no le sale la foto HD de la pizarra? No escribe nada.

Abrir la ficha de una tarea encola una foto: Playwright abre el editor de verdad y fotografía
la pizarra. Cuando eso falla, el sistema guarda el motivo en caché y se toma un descanso para
no levantar Chromium en cada visita. Este comando lee ese motivo y ese descanso.

Probado en producción: la tarea 599 pasó de un placeholder de 16 KB a su dibujo real de 44 KB
sólo con abrir su ficha. La 711 no. Esto dice por qué.

    python3 manage.py revisar_foto_pizarra --ids 711,963,599
"""
from django.core.cache import cache
from django.core.management.base import BaseCommand

from football.models import SessionTask


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
            castigada = bool(cache.get(foto._fail_key(tid)))
            motivo = cache.get(foto._last_error_key(tid)) or "(sin motivo guardado)"
            al_dia = False
            try:
                al_dia = bool(foto.snapshot_is_current(tarea))
            except Exception:
                pass

            self.stdout.write(self.style.SUCCESS(f"{tid:>6}  {str(tarea.title or '')[:48]}"))
            self.stdout.write(f"        objetos en la pizarra : {objetos}")
            self.stdout.write(f"        tiempo que se le da   : {limite_ms // 1000}s (+{reposo_ms}ms de reposo)")
            self.stdout.write(f"        foto al día           : {'sí' if al_dia else 'NO'}")
            self.stdout.write(f"        en penitencia         : {'SÍ (no reintenta hasta que caduque)' if castigada else 'no'}")
            self.stdout.write(f"        último motivo         : {motivo}")
            self.stdout.write("")

        self.stdout.write("Este comando no ha escrito nada.")
