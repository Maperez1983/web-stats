from __future__ import annotations

from django.core.management.base import BaseCommand

from football.models import Workspace


class Command(BaseCommand):
    help = "Activa el módulo Academia para todos los workspaces de tipo club (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simula cambios sin escribir en BD.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        qs = Workspace.objects.filter(kind=Workspace.KIND_CLUB).order_by("id")
        total = qs.count()
        changed = 0
        for ws in qs.iterator():
            enabled = getattr(ws, "enabled_modules", None)
            if not isinstance(enabled, dict):
                enabled = {}
            if enabled.get("academy") is True:
                continue
            enabled["academy"] = True
            changed += 1
            if dry_run:
                continue
            ws.enabled_modules = enabled
            ws.save(update_fields=["enabled_modules", "updated_at"])

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: activar academia en {changed}/{total} workspaces (club)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"OK: academia activada en {changed}/{total} workspaces (club)."))

