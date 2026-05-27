from __future__ import annotations

from datetime import time
from pathlib import Path

from django.core.files.base import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from football.models import ImportedSessionDocument, SessionTask, Team, TrainingMicrocycle, TrainingSession


class Command(BaseCommand):
    help = "Importa un PDF de sesión y lo transforma en una TrainingSession + tareas (para pruebas en local)."

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", help="Ruta al PDF de sesión.")
        parser.add_argument("--team-id", type=int, default=0, help="Team.id destino (si no, usa el equipo primario).")
        parser.add_argument(
            "--repo",
            default=ImportedSessionDocument.REPO_TRADITIONAL,
            choices=[ImportedSessionDocument.REPO_TRADITIONAL, ImportedSessionDocument.REPO_INTERACTIVE],
            help="Repositorio del doc importado.",
        )
        parser.add_argument("--title", default="", help="Título (si vacío, usa el nombre del PDF).")
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada; solo valida el parseo.")

    def handle(self, *args, **options):
        pdf_path = Path(str(options["pdf_path"])).expanduser().resolve()
        if not pdf_path.exists():
            raise CommandError(f"No existe: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise CommandError(f"No es PDF: {pdf_path}")

        team_id = int(options.get("team_id") or 0)
        repository = str(options.get("repo") or ImportedSessionDocument.REPO_TRADITIONAL).strip() or ImportedSessionDocument.REPO_TRADITIONAL
        title = str(options.get("title") or "").strip()
        dry_run = bool(options.get("dry_run"))

        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).order_by("id").first()
        if not team:
            raise CommandError("No se encontró equipo. Usa --team-id.")

        from football.session_import_services import (
            INBOX_MICROCYCLE_WEEK_START,
            LIBRARY_REPOSITORY_TRADITIONAL,
            apply_analysis_to_task,
            extract_pdf_text,
            extract_preview_images_from_pdf,
            extract_tasks_from_pdf_text,
            get_or_create_inbox_microcycle,
            get_or_create_week_microcycle,
            learn_task_blueprint_from_pdf_import,
            next_session_task_order,
            parse_pdf_session_header_fields,
            serialize_session_plan_fields,
            suggest_blocks_for_session_pdf_segments,
            suggest_session_plan_fields_from_pdf_text,
        )

        resolved_title = title or pdf_path.stem
        resolved_title = resolved_title.strip()[:180] or pdf_path.stem[:180]

        with open(pdf_path, "rb") as fh:
            upload = File(fh, name=pdf_path.name)
            extracted_text = extract_pdf_text(upload, max_chars=60000)
            header = parse_pdf_session_header_fields(extracted_text) if extracted_text else {}

            session_date = (header.get("date") if isinstance(header, dict) else None) or timezone.localdate()
            plan_fields = suggest_session_plan_fields_from_pdf_text(extracted_text, imported_doc_id=None)
            content = serialize_session_plan_fields(plan_fields)

            md = header.get("md") if isinstance(header, dict) else None
            sess_no = header.get("session_number") if isinstance(header, dict) else None
            md_label = ""
            if isinstance(md, int):
                md_label = "MD" if md == 0 else f"MD{md:+d}".replace("MD+-", "MD-")
            focus = ""
            if isinstance(sess_no, int) and sess_no > 0:
                focus = f"{md_label} · Sesión {sess_no}" if md_label else f"Sesión {sess_no}"
            if not focus:
                focus = resolved_title
            focus = focus.strip()[:140] or resolved_title[:140] or "Sesión importada"

            parsed_tasks = extract_tasks_from_pdf_text(extracted_text, fallback_title=focus) or []
            duration_minutes = 90
            if parsed_tasks:
                total = 0
                for seg in parsed_tasks:
                    analysis = seg.get("analysis") if isinstance(seg, dict) else {}
                    try:
                        total += max(0, int(analysis.get("minutes") or 0))
                    except Exception:
                        continue
                if total >= 15:
                    duration_minutes = min(240, total)

            microcycle = (
                TrainingMicrocycle.objects
                .filter(team=team, week_start__lte=session_date, week_end__gte=session_date)
                .exclude(week_start=INBOX_MICROCYCLE_WEEK_START)
                .order_by("-week_start", "-id")
                .first()
            )
            if not microcycle:
                title_hint = ""
                try:
                    mc_num = int((header or {}).get("microcycle_number") or 0)
                except Exception:
                    mc_num = 0
                if mc_num:
                    title_hint = f"Microciclo Nº{mc_num}"
                microcycle = get_or_create_week_microcycle(team, session_date, title_hint=title_hint) or get_or_create_inbox_microcycle(team)
            if not microcycle:
                raise CommandError("No se pudo preparar el microciclo destino.")

            if dry_run:
                self.stdout.write(self.style.WARNING("dry-run: no se guardará nada."))
                self.stdout.write(self.style.SUCCESS(f"OK parseo: date={session_date} focus={focus} duration={duration_minutes}m tasks={len(parsed_tasks)}"))
                return

            with transaction.atomic():
                doc = ImportedSessionDocument.objects.create(
                    team=team,
                    repository=repository,
                    title=resolved_title,
                    session_date=session_date,
                    pdf=upload,
                )

                next_order = (TrainingSession.objects.filter(microcycle=microcycle).aggregate(Max("order")).get("order__max") or 0) + 1
                session = TrainingSession.objects.create(
                    microcycle=microcycle,
                    session_date=session_date,
                    start_time=(header.get("time") if isinstance(header.get("time"), time) else None),
                    duration_minutes=duration_minutes,
                    intensity=TrainingSession.INTENSITY_MEDIUM,
                    focus=focus,
                    content=content,
                    status=TrainingSession.STATUS_PLANNED,
                    order=next_order,
                )

                if not parsed_tasks:
                    parsed_tasks = [
                        {
                            "analysis": {
                                "title": focus[:160],
                                "objective": "",
                                "minutes": 15,
                                "coaching_points": "",
                                "confrontation_rules": "",
                                "summary": "",
                            },
                            "raw_text": "",
                            "segment_index": 1,
                            "segment_total": 1,
                        }
                    ]

                try:
                    if hasattr(doc.pdf, "open"):
                        doc.pdf.open("rb")
                except Exception:
                    pass
                try:
                    if hasattr(doc.pdf, "seek"):
                        doc.pdf.seek(0)
                except Exception:
                    pass

                preview_payloads = extract_preview_images_from_pdf(doc.pdf, max_images=max(1, len(parsed_tasks)), prefer_render=True)
                segment_blocks = suggest_blocks_for_session_pdf_segments(parsed_tasks, SessionTask.BLOCK_MAIN_1)
                base_order = next_session_task_order(session) - 1
                shared_pdf_name = str(getattr(doc.pdf, "name", "") or "").strip()

                for idx, segment in enumerate(parsed_tasks, start=1):
                    analysis = segment.get("analysis") or {}
                    seg_title = str(analysis.get("title") or f"{focus} · Tarea {idx}").strip()[:160] or f"{focus} · Tarea {idx}"
                    minutes = max(5, min(int(analysis.get("minutes") or 15), 90))
                    segment_index = max(1, int(segment.get("segment_index") or idx))
                    segment_total = max(1, int(segment.get("segment_total") or len(parsed_tasks)))
                    block = segment_blocks[min(idx - 1, len(segment_blocks) - 1)] if segment_blocks else SessionTask.BLOCK_MAIN_1

                    extra_layout = {
                        "meta": {
                            "scope": "coach",
                            "source": "import_session_pdf_cmd",
                            "import_mode": "session_pdf",
                            "repository": repository or LIBRARY_REPOSITORY_TRADITIONAL,
                            "pdf_source_name": resolved_title[:220],
                            "pdf_segment_index": segment_index,
                            "pdf_segments_total": segment_total,
                            "pdf_segment_excerpt": (segment.get("raw_text") or "")[:1200],
                            "pdf_split_done": True,
                            "imported_session_doc_id": int(doc.id),
                        }
                    }
                    task = SessionTask.objects.create(
                        session=session,
                        title=seg_title,
                        block=block,
                        duration_minutes=minutes,
                        objective=str(analysis.get("objective") or "").strip()[:180],
                        coaching_points=str(analysis.get("coaching_points") or ""),
                        confrontation_rules=str(analysis.get("confrontation_rules") or ""),
                        tactical_layout=extra_layout,
                        task_pdf=shared_pdf_name or None,
                        status=SessionTask.STATUS_PLANNED,
                        order=base_order + idx,
                        notes=f"Importada desde sesión PDF #{doc.id}",
                    )
                    if isinstance(analysis, dict) and analysis:
                        try:
                            apply_analysis_to_task(task, analysis)
                        except Exception:
                            pass
                        try:
                            learn_task_blueprint_from_pdf_import(team=team, task=task, analysis=analysis, scope_key="coach", actor_username="")
                        except Exception:
                            pass

                    payload = preview_payloads[min(idx - 1, len(preview_payloads) - 1)] if preview_payloads else None
                    if payload:
                        preview_name, preview_content = payload
                        try:
                            preview_content.seek(0)
                        except Exception:
                            pass
                        try:
                            task.task_preview_image.save(preview_name, preview_content, save=True)
                        except Exception:
                            pass

        self.stdout.write(self.style.SUCCESS(f"OK doc={doc.id} session={session.id}"))
