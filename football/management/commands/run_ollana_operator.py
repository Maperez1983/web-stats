from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError

from football.models import Workspace
from football.system_guard import run_continuous_operator_cycle


class Command(BaseCommand):
    help = "Ejecuta el operador continuo de Ollana sobre un workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True, help="Workspace.id objetivo.")
        parser.add_argument("--actor-id", type=int, default=0, help="User.id que figura como actor del operador.")
        parser.add_argument("--iterations", type=int, default=1, help="Número de ciclos a ejecutar.")
        parser.add_argument("--sleep-seconds", type=int, default=0, help="Espera entre ciclos.")
        parser.add_argument("--daemon", action="store_true", help="Mantiene el operador corriendo hasta stop flag o max runtime.")
        parser.add_argument("--max-runtime-seconds", type=int, default=0, help="Límite total del modo daemon.")
        parser.add_argument("--force", action="store_true", help="Fuerza lease del operador.")
        parser.add_argument("--holder", type=str, default="ollana-operator", help="Identificador del proceso operador.")

    def handle(self, *args, **options):
        workspace_id = int(options.get("workspace_id") or 0)
        actor_id = int(options.get("actor_id") or 0)
        iterations = max(1, int(options.get("iterations") or 1))
        sleep_seconds = max(0, int(options.get("sleep_seconds") or 0))
        daemon = bool(options.get("daemon"))
        max_runtime_seconds = max(0, int(options.get("max_runtime_seconds") or 0))
        force = bool(options.get("force"))
        holder = str(options.get("holder") or "ollana-operator").strip() or "ollana-operator"

        workspace = Workspace.objects.filter(id=workspace_id).first()
        if not workspace:
            raise CommandError(f"Workspace {workspace_id} no encontrado.")

        started_ts = time.time()
        cycle_index = 0
        while True:
            cycle_index += 1
            result = run_continuous_operator_cycle(
                workspace=workspace,
                actor_id=actor_id,
                page_context={
                    "page": "continuous-operator-command",
                    "workspace_id": int(workspace.id),
                    "workspace_name": str(workspace.name or "")[:160],
                    "user_id": actor_id,
                    "is_admin_user": True,
                    "can_manage_guard": True,
                    "can_operate_guard_code": True,
                },
                holder=holder,
                force=force,
            )
            if not result.get("ok"):
                if daemon and str(result.get("reason") or "") == "stop_requested":
                    self.stdout.write("stop_requested recibido. Operador continuo detenido.")
                    break
                raise CommandError(f"Operador continuo no ejecutado: {result.get('reason')}")
            runtime = result.get("runtime") or {}
            proactive = result.get("proactive") or {}
            queue_counts = proactive.get("queue_counts") or {}
            self.stdout.write(
                f"cycle {cycle_index}/{iterations if not daemon else 'daemon'} · status={runtime.get('last_status')} · "
                f"detections={runtime.get('last_detection_count', 0)} · "
                f"backlog={runtime.get('last_executed_tasks', 0)} · "
                f"pending={queue_counts.get('pending', 0)} blocked={queue_counts.get('blocked', 0)}"
            )
            if not daemon and cycle_index >= iterations:
                break
            if daemon and max_runtime_seconds and (time.time() - started_ts) >= max_runtime_seconds:
                self.stdout.write("max_runtime_seconds alcanzado. Operador continuo detenido.")
                break
            if sleep_seconds:
                time.sleep(sleep_seconds)

        self.stdout.write(self.style.SUCCESS("Operador continuo de Ollana completado."))
