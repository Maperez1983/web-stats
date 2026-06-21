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
        parser.add_argument("--force", action="store_true", help="Fuerza lease del operador.")
        parser.add_argument("--holder", type=str, default="ollana-operator", help="Identificador del proceso operador.")

    def handle(self, *args, **options):
        workspace_id = int(options.get("workspace_id") or 0)
        actor_id = int(options.get("actor_id") or 0)
        iterations = max(1, int(options.get("iterations") or 1))
        sleep_seconds = max(0, int(options.get("sleep_seconds") or 0))
        force = bool(options.get("force"))
        holder = str(options.get("holder") or "ollana-operator").strip() or "ollana-operator"

        workspace = Workspace.objects.filter(id=workspace_id).first()
        if not workspace:
            raise CommandError(f"Workspace {workspace_id} no encontrado.")

        for index in range(iterations):
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
                raise CommandError(f"Operador continuo no ejecutado: {result.get('reason')}")
            runtime = result.get("runtime") or {}
            proactive = result.get("proactive") or {}
            queue_counts = proactive.get("queue_counts") or {}
            self.stdout.write(
                f"cycle {index + 1}/{iterations} · status={runtime.get('last_status')} · "
                f"detections={runtime.get('last_detection_count', 0)} · "
                f"backlog={runtime.get('last_executed_tasks', 0)} · "
                f"pending={queue_counts.get('pending', 0)} blocked={queue_counts.get('blocked', 0)}"
            )
            if sleep_seconds and index < iterations - 1:
                time.sleep(sleep_seconds)

        self.stdout.write(self.style.SUCCESS("Operador continuo de Ollana completado."))
