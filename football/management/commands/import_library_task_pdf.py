from __future__ import annotations

from pathlib import Path

from django.core.files.base import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from football.models import SessionTask, Team


class Command(BaseCommand):
    help = "Importa uno o varios PDFs como tareas en Biblioteca (1 PDF = 1 tarea por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("pdf_paths", nargs="+", help="Rutas a PDFs a importar.")
        parser.add_argument("--team-id", type=int, default=0, help="Team.id destino (si no, usa el equipo primario).")
        parser.add_argument(
            "--scope",
            default="coach",
            choices=["coach", "goalkeeper", "fitness", "abp", "any"],
            help="Scope destino para Biblioteca.",
        )
        parser.add_argument(
            "--repo",
            default="traditional",
            choices=["traditional", "interactive", "ai_trainer"],
            help="Repositorio Biblioteca destino.",
        )
        parser.add_argument(
            "--mode",
            default="raw",
            choices=["raw", "analyze"],
            help="raw: 1 PDF = 1 tarea; analyze: intenta extraer varias tareas del PDF.",
        )
        parser.add_argument("--title", default="", help="Título base (si vacío, usa el nombre del PDF).")
        parser.add_argument("--objective", default="", help="Objetivo base.")
        parser.add_argument(
            "--block",
            default=SessionTask.BLOCK_MAIN_1,
            choices=[c[0] for c in SessionTask.BLOCK_CHOICES],
            help="Bloque por defecto.",
        )
        parser.add_argument("--minutes", type=int, default=15, help="Duración por defecto en minutos.")
        parser.add_argument(
            "--recreate-board",
            action="store_true",
            help="Intenta recrear pizarra desde la preview (si es posible).",
        )
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios; solo valida.")

    def handle(self, *args, **options):
        pdf_paths = [str(p) for p in (options.get("pdf_paths") or []) if str(p).strip()]
        if not pdf_paths:
            raise CommandError("Indica al menos un PDF.")

        team_id = int(options.get("team_id") or 0)
        scope_key = str(options.get("scope") or "coach").strip().lower() or "coach"
        repository = str(options.get("repo") or "traditional").strip().lower() or "traditional"
        import_mode = str(options.get("mode") or "raw").strip().lower() or "raw"
        title = str(options.get("title") or "").strip()
        objective = str(options.get("objective") or "").strip()
        block = str(options.get("block") or SessionTask.BLOCK_MAIN_1).strip()
        minutes = int(options.get("minutes") or 15)
        recreate_board = bool(options.get("recreate_board"))
        dry_run = bool(options.get("dry_run"))

        if block not in {c[0] for c in SessionTask.BLOCK_CHOICES}:
            raise CommandError(f"Bloque inválido: {block}")
        minutes = max(5, min(int(minutes), 90))

        if team_id:
            team = Team.objects.filter(id=team_id).first()
        else:
            team = Team.objects.filter(is_primary=True).order_by("id").first()
        if not team:
            raise CommandError("No se encontró equipo. Usa --team-id.")

        from football.session_import_services import (
            ensure_library_task_preview,
            get_or_create_library_session_with_repository,
            import_library_tasks_from_pdf_advanced,
        )

        target_session = get_or_create_library_session_with_repository(team, scope_key, repository=repository)
        if not target_session:
            raise CommandError("No se pudo resolver la sesión interna de Biblioteca.")

        base_order = SessionTask.objects.filter(session=target_session).count()

        resolved_paths: list[Path] = []
        for raw in pdf_paths:
            p = Path(raw).expanduser().resolve()
            if not p.exists():
                raise CommandError(f"No existe: {p}")
            if p.suffix.lower() != ".pdf":
                raise CommandError(f"No es PDF: {p}")
            resolved_paths.append(p)

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: no se guardará nada."))

        created = 0
        processed = 0

        with transaction.atomic():
            if import_mode == "analyze":
                pdf_files: list[File] = []
                handles = []
                try:
                    for p in resolved_paths:
                        fh = open(p, "rb")
                        handles.append(fh)
                        pdf_files.append(File(fh, name=p.name))
                    result = import_library_tasks_from_pdf_advanced(
                        primary_team=team,
                        scope_key=scope_key,
                        target_session=target_session,
                        pdf_files=pdf_files,
                        title=title[:160],
                        objective=objective[:180],
                        block=block,
                        minutes=minutes,
                        recreate_board=recreate_board,
                        base_order=base_order,
                    )
                    created = int((result or {}).get("created_count") or 0)
                    processed = int((result or {}).get("processed_pdfs") or 0)
                finally:
                    for fh in handles:
                        try:
                            fh.close()
                        except Exception:
                            pass
            else:
                for idx, p in enumerate(resolved_paths, start=1):
                    processed += 1
                    file_stem = p.stem.strip() or f"Tarea PDF {idx}"
                    task_title = (title or file_stem).strip()
                    if title and len(resolved_paths) > 1:
                        task_title = f"{title} · {file_stem}"
                    task_title = (task_title[:160] or f"Tarea PDF {idx}")

                    with open(p, "rb") as fh:
                        pdf_file = File(fh, name=p.name)
                        layout = {
                            "meta": {
                                "scope": scope_key,
                                "source": "pdf_import",
                                "import_mode": "raw",
                                "repository": repository,
                                "pdf_source_name": p.name,
                            }
                        }
                        task = SessionTask.objects.create(
                            session=target_session,
                            title=task_title,
                            block=block,
                            duration_minutes=minutes,
                            objective=objective[:180],
                            coaching_points="",
                            confrontation_rules="",
                            tactical_layout=layout,
                            task_pdf=pdf_file,
                            status=SessionTask.STATUS_PLANNED,
                            order=base_order + created + 1,
                            notes="Importada desde PDF (CLI).",
                        )
                        try:
                            ensure_library_task_preview(task, force=True, prefer_render=True)
                        except Exception:
                            pass
                        created += 1

            if dry_run:
                raise CommandError("dry-run: rollback intencional (no se guardaron cambios).")

        self.stdout.write(
            self.style.SUCCESS(
                f"Importación OK. team#{team.id} repo={repository} scope={scope_key} mode={import_mode} "
                f"processed={processed} created={created}"
            )
        )
