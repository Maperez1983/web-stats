from __future__ import annotations

from django.core.management.base import BaseCommand

from football.models import Workspace
from football.workspace_split import (
    apply_split_workspace_plan,
    build_split_workspace_plan,
)


class Command(BaseCommand):
    help = (
        "Convierte un workspace club multi-equipo (categorías) en varios clubs independientes "
        "(1 club = 1 equipo). No borra partidos/jugadores: solo reordena workspaces y accesos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, default=0, help="ID del workspace origen.")
        parser.add_argument("--workspace-slug", type=str, default="", help="Slug del workspace origen.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica cambios. Si no, solo muestra el plan (dry-run).",
        )
        parser.add_argument(
            "--disable-source-workspace",
            action="store_true",
            help="Marca el workspace origen como inactivo al terminar (recomendado cuando ya no se use).",
        )
        parser.add_argument(
            "--include-primary",
            action="store_true",
            help="También genera un club para el primary_team (avanzado). Requiere dejar el origen sin primary_team.",
        )

    def handle(self, *args, **options):
        workspace_id = int(options.get("workspace_id") or 0)
        workspace_slug = str(options.get("workspace_slug") or "").strip()
        apply_changes = bool(options.get("apply"))
        disable_source = bool(options.get("disable_source_workspace"))
        include_primary = bool(options.get("include_primary"))

        qs = Workspace.objects.select_related("owner_user", "primary_team").filter(kind=Workspace.KIND_CLUB)
        workspace = qs.filter(id=workspace_id).first() if workspace_id else qs.filter(slug=workspace_slug).first()
        if not workspace:
            raise RuntimeError("Workspace origen no encontrado (usa --workspace-id o --workspace-slug).")

        plan = build_split_workspace_plan(workspace, include_primary=include_primary)
        if not plan:
            self.stdout.write(self.style.WARNING("El workspace no tiene múltiples equipos; no hay nada que separar."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Plan de separación · Workspace: {workspace.name} (id={workspace.id})"))
        for row in plan:
            context_label = "sí" if row.has_context else "no"
            self.stdout.write(
                f"- Team {row.team_id}: {row.team_category or '-'} · {row.team_name} -> "
                f"Workspace '{row.new_workspace_name}' (slug={row.new_workspace_slug}) "
                f"[miembros={len(row.member_user_ids)}, staff={row.staff_count}, contexto={context_label}]"
            )
        self.stdout.write("")
        if not apply_changes:
            self.stdout.write(self.style.WARNING("Dry-run: añade --apply para ejecutar cambios."))
            return

        created = apply_split_workspace_plan(
            workspace,
            plan,
            disable_source_workspace=disable_source,
            include_primary=include_primary,
        )
        if not created:
            self.stdout.write(self.style.WARNING("No se crearon clubs (nada que aplicar)."))
            return
        self.stdout.write(self.style.SUCCESS("Separación completada. Revisa Platform: ahora verás clubs separados."))

