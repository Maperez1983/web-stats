"""Hace las fotos HD de pizarra que hay apuntadas en la cola.

Este es el proceso que CUMPLE los encargos que deja el web. Antes no existía: la foto se hacía
en un hilo dentro del propio servidor web, y eso tenía dos finales malos —el worker se reiniciaba
y el hilo moría sin dejar rastro, o Chromium competía por la memoria con la app que tenía que
servirle la página del editor—. Ver el porqué completo en `models.TaskBoardShot`.

    python manage.py fotos_pizarra                 # vacía la cola y sale
    python manage.py fotos_pizarra --bucle         # se queda vaciándola (para el worker)
    python manage.py fotos_pizarra --sembrar       # apunta TODAS las tareas sin foto al día
    python manage.py fotos_pizarra --estado        # sólo cuenta cómo va la cola, no fotografía

La URL a la que se asoma sale de `BOARD_SHOT_BASE_URL`. Tiene que ser la del sitio de verdad
(https://app.segundajugada.es): el editor se abre por HTTP como lo abriría una persona.
"""
import os
import time

from django.core.management.base import BaseCommand
from django.db.models import Count

from football import task_board_snapshot as fotos
from football.models import SessionTask, TaskBoardShot


def _base_url() -> str:
    url = str(os.getenv("BOARD_SHOT_BASE_URL") or "").strip().rstrip("/")
    if url:
        return url
    host = str(os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    if host:
        return f"https://{host}"
    return ""


class Command(BaseCommand):
    help = "Hace las fotos HD de pizarra apuntadas en la cola."

    def add_arguments(self, parser):
        parser.add_argument("--bucle", action="store_true", help="No sale: sigue vaciando la cola.")
        parser.add_argument("--espera", type=int, default=60, help="Segundos entre vueltas en --bucle.")
        parser.add_argument("--max", type=int, default=0, help="Como mucho N fotos (0 = sin tope).")
        parser.add_argument("--sembrar", action="store_true", help="Apunta todas las tareas sin foto al día.")
        parser.add_argument("--estado", action="store_true", help="Sólo informa de cómo va la cola.")
        parser.add_argument("--tarea", type=int, default=0, help="Sólo esta tarea (para depurar).")

    # -- informar -----------------------------------------------------------
    def _estado(self):
        por_estado = dict(
            TaskBoardShot.objects.values_list("state").annotate(n=Count("id")).values_list("state", "n")
        )
        self.stdout.write(f"cola: {por_estado or 'vacía'}")
        rendidas = TaskBoardShot.objects.filter(state=TaskBoardShot.RENDIDA).order_by("-updated_at")[:10]
        if rendidas:
            self.stdout.write("se rindieron (últimas 10):")
            for s in rendidas:
                self.stdout.write(f"   tarea {s.task_id}: {s.last_error}")

    # -- sembrar ------------------------------------------------------------
    def _sembrar(self):
        """Apunta las tareas que no tienen foto al día.

        `requested_by` se queda vacío a propósito: aquí no hay nadie pidiendo nada, y la foto
        necesita la sesión de una persona con permiso. Se rellena en cuanto alguien abre la
        ficha. Sembrar sirve para que la cola refleje el trabajo real, no para saltarse permisos.
        """
        vistas = encoladas = 0
        for task in SessionTask.objects.order_by("-id").iterator():
            vistas += 1
            if fotos.snapshot_is_current(task):
                continue
            if fotos.request_snapshot(task) is not None:
                encoladas += 1
        self.stdout.write(f"revisadas {vistas} tareas · apuntadas {encoladas}")
        sin_dueno = TaskBoardShot.objects.filter(
            state=TaskBoardShot.PENDIENTE, requested_by__isnull=True
        ).count()
        if sin_dueno:
            self.stdout.write(
                f"OJO: {sin_dueno} encargos sin quién los pidió. Esos esperan a que alguien "
                "con permiso abra la ficha una vez; hasta entonces no hay sesión con la que "
                "abrir el editor."
            )

    # -- trabajar -----------------------------------------------------------
    def _una_vuelta(self, base_url, tope=0, hechas=0):
        """Coge encargos y los cumple de UNO EN UNO. Devuelve cuántas fotos salieron."""
        salieron = 0
        while True:
            if tope and (hechas + salieron) >= tope:
                return salieron
            cogidos = fotos.claim_pending(limit=1)
            if not cogidos:
                return salieron
            shot = cogidos[0]
            comienzo = time.monotonic()
            try:
                ok, nota = fotos.cumplir_encargo(shot, base_url)
            except Exception as exc:  # nunca dejamos un encargo alquilado por una excepción
                ok, nota = False, f"{type(exc).__name__}: {exc}"
            tardo = time.monotonic() - comienzo
            if not ok and nota == "__en_cola__":
                # No se intento porque habia otra foto delante. `cumplir_encargo` ya la devolvio
                # a la cola sin gastar intento; aqui solo dejamos de dar vueltas en esta pasada.
                self.stdout.write(f"  tarea {shot.task_id}: en cola, había otra delante")
                return salieron
            if ok:
                fotos.mark_done(shot)
                salieron += 1
                self.stdout.write(f"  tarea {shot.task_id}: {nota} ({tardo:.0f}s)")
            else:
                fotos.mark_failed(shot, nota)
                shot.refresh_from_db()
                cola = (
                    "se rinde" if shot.state == TaskBoardShot.RENDIDA
                    else f"reintento {shot.attempts}/{TaskBoardShot.MAX_INTENTOS}"
                )
                self.stderr.write(f"  tarea {shot.task_id}: {nota} ({tardo:.0f}s, {cola})")

    def handle(self, *args, **opts):
        if opts["estado"]:
            self._estado()
            return
        if opts["sembrar"]:
            self._sembrar()
            return

        base_url = _base_url()
        if not base_url:
            self.stderr.write(
                "Falta BOARD_SHOT_BASE_URL (p. ej. https://app.segundajugada.es). "
                "La foto abre el editor por HTTP, así que necesita saber a qué sitio asomarse."
            )
            return

        if opts["tarea"]:
            task = SessionTask.objects.filter(pk=opts["tarea"]).first()
            if not task:
                self.stderr.write(f"no existe la tarea {opts['tarea']}")
                return
            fotos.request_snapshot(task, force=True)

        tope = max(0, int(opts["max"] or 0))
        hechas = 0
        while True:
            hechas += self._una_vuelta(base_url, tope=tope, hechas=hechas)
            if not opts["bucle"] or (tope and hechas >= tope):
                break
            time.sleep(max(5, int(opts["espera"])))
        self.stdout.write(f"fotos hechas: {hechas}")
