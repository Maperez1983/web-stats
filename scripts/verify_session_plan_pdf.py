#!/usr/bin/env python3
"""
Verificación local del PDF UEFA/RFEF de una sesión.

Uso:
  DEBUG=true SECRET_KEY=dev ALLOWED_HOSTS=localhost \
    .venv/bin/python scripts/verify_session_plan_pdf.py --session-id 8 --out /tmp/sesion-8.pdf

Valida:
  - Orden de secciones (Calentamiento → Activación → Principal 1 → Principal 2 → Vuelta a la calma → Otros)
  - Que "Descripción gráfica", "Consigna / explicación" y "Detalles del ejercicio" no se separen en páginas distintas.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _normalize(s: str) -> str:
    return " ".join(str(s or "").split()).strip().casefold()


def _extract_section_name(page_text: str) -> str:
    # En el PDF suele aparecer: "DETALLES DE LA SECCIÓN\nNombre Activación\n..."
    text = str(page_text or "")
    # Allow accents: SECCIÓN/SECCION
    m = re.search(r"DETALLES\s+DE\s+LA\s+SECCI[ÓO]N\s*[\r\n]+Nombre\s+([^\r\n]+)", text, flags=re.IGNORECASE)
    if not m:
        # Fallback: a veces todo va en una línea
        m = re.search(r"DETALLES\s+DE\s+LA\s+SECCI[ÓO]N\s+Nombre\s+([^\r\n]+)", text, flags=re.IGNORECASE)
    return (m.group(1).strip() if m else "").strip()


def _validate_pdf(pdf_path: Path) -> tuple[bool, list[str]]:
    from pypdf import PdfReader  # imported here to keep script start fast

    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        return False, ["PDF vacío o no legible."]

    errors: list[str] = []
    order_map = {
        "calentamiento": 1,
        "activación": 2,
        "activacion": 2,
        "principal 1": 3,
        "principal1": 3,
        "principal 2": 4,
        "principal2": 4,
        "vuelta a la calma": 5,
        "vuelta calma": 5,
        "otros": 6,
    }

    last_rank = 0
    seen_sections: list[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        folded = _normalize(text)

        section = _extract_section_name(text)
        if section:
            section_norm = _normalize(section).replace("·", " ").strip()
            # Normaliza variantes habituales
            section_norm = section_norm.replace("vuelta a la calma", "vuelta a la calma")
            rank = order_map.get(section_norm, 99)
            if rank < last_rank:
                errors.append(
                    f"Orden incorrecto en página {page_index}: '{section}' aparece después de '{seen_sections[-1] if seen_sections else ''}'."
                )
            last_rank = max(last_rank, rank)
            seen_sections.append(section)

        # Split check: si aparece "Descripción gráfica" pero no el resto en la misma página, es un corte.
        has_graphic = "descripción gráfica" in folded or "descripcion grafica" in folded
        if has_graphic:
            has_consigna = "consigna / explicación" in folded or "consigna / explicacion" in folded
            has_details = "detalles del ejercicio" in folded
            if not has_consigna or not has_details:
                errors.append(
                    f"Corte de secciones en página {page_index}: gráfica={has_graphic}, consigna={has_consigna}, detalles_ejercicio={has_details}."
                )

    if not seen_sections:
        errors.append("No se pudo detectar 'DETALLES DE LA SECCIÓN / Nombre ...' en ninguna página.")

    return (len(errors) == 0), errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", type=int, default=0)
    parser.add_argument("--import-pdf", type=str, default="", help="Ruta a un PDF para importar a una sesión temporal y verificar el PDF resultante.")
    parser.add_argument("--cleanup", action="store_true", help="Borra la sesión temporal creada con --import-pdf al terminar (recomendado).")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    # Defaults para ejecutar en local sin tener que exportar todo.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webstats.settings")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("SECRET_KEY", "dev-insecure-change-me")
    os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")

    # Igual que `manage.py`: prepara paths nativos (WeasyPrint/Cairo, cache, etc.)
    try:
        from webstats.runtime_env import configure_native_runtime

        configure_native_runtime()
    except Exception:
        pass

    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.core.files.base import ContentFile
    from django.template.loader import render_to_string
    from django.test.client import RequestFactory

    from football.models import Team, TrainingMicrocycle, TrainingSession, SessionTask
    from football.views import _build_session_pdf_context, _render_pdf_bytes_with_error
    from football.views import (
        _extract_pdf_text,
        _extract_tasks_from_pdf_text,
        _extract_preview_images_from_pdf,
        _apply_analysis_to_task,
        _suggest_blocks_for_session_pdf_segments,
    )
    from django.utils import timezone
    from datetime import timedelta

    created_session = None
    created_task_ids: list[int] = []

    if args.import_pdf:
        pdf_path = Path(args.import_pdf).expanduser()
        if not pdf_path.exists():
            print(f"ERROR: PDF no encontrado: {pdf_path}", file=sys.stderr)
            return 2
        team = Team.objects.filter(is_primary=True).first() or Team.objects.first()
        if not team:
            print("ERROR: no hay equipos en BD.", file=sys.stderr)
            return 2
        today = timezone.localdate()
        micro = (
            TrainingMicrocycle.objects.filter(team=team).order_by("-week_start", "-id").first()
            or TrainingMicrocycle.objects.create(
                team=team,
                week_start=today,
                week_end=today + timedelta(days=6),
                title="TMP PDF import",
                objective="",
                status=getattr(TrainingMicrocycle, "STATUS_DRAFT", "draft"),
                notes="",
            )
        )
        created_session = TrainingSession.objects.create(
            microcycle=micro,
            session_date=today,
            focus=f"TMP · Verificación PDF · {pdf_path.stem}"[:140],
            duration_minutes=90,
            content="",
            status=getattr(TrainingSession, "STATUS_PLANNED", "planned"),
            order=999,
        )
        raw = pdf_path.read_bytes()
        extracted_text = ""
        try:
            extracted_text = _extract_pdf_text(ContentFile(raw, name=pdf_path.name), max_chars=60000)
        except Exception:
            extracted_text = ""
        parsed_tasks = _extract_tasks_from_pdf_text(extracted_text, fallback_title=pdf_path.stem)
        if not parsed_tasks:
            parsed_tasks = [
                {
                    "analysis": {"title": pdf_path.stem[:160], "objective": "", "minutes": 15, "coaching_points": "", "confrontation_rules": ""},
                    "raw_text": extracted_text[:2500],
                    "segment_index": 1,
                    "segment_total": 1,
                }
            ]
        suggested_blocks = _suggest_blocks_for_session_pdf_segments(parsed_tasks, SessionTask.BLOCK_MAIN_1) or []
        preview_payloads = []
        try:
            preview_payloads = _extract_preview_images_from_pdf(
                ContentFile(raw, name=pdf_path.name),
                max_images=max(1, len(parsed_tasks)),
                prefer_render=False,
            )
        except Exception:
            preview_payloads = []

        for idx, chunk in enumerate(parsed_tasks, start=1):
            analysis = chunk.get("analysis") or {}
            title = str(analysis.get("title") or f"{pdf_path.stem} · Tarea {idx}")[:160]
            minutes = int(analysis.get("minutes") or 15)
            block = suggested_blocks[idx - 1] if idx - 1 < len(suggested_blocks) else SessionTask.BLOCK_MAIN_1
            task = SessionTask.objects.create(
                session=created_session,
                title=title,
                block=block,
                duration_minutes=max(5, min(minutes, 90)),
                objective=str(analysis.get("objective") or "")[:180],
                coaching_points=str(analysis.get("coaching_points") or ""),
                confrontation_rules=str(analysis.get("confrontation_rules") or ""),
                tactical_layout={
                    "meta": {
                        "scope": "coach",
                        "pdf_source_name": pdf_path.name,
                        "pdf_segment_index": idx,
                        "pdf_segments_total": len(parsed_tasks),
                        "pdf_segment_excerpt": str(chunk.get("raw_text") or "")[:1200],
                        "pdf_split_done": True,
                    }
                },
                status=getattr(SessionTask, "STATUS_PLANNED", "planned"),
                order=idx,
                notes="TMP import para verificación",
            )
            try:
                _apply_analysis_to_task(task, analysis)
            except Exception:
                pass
            try:
                meta = (task.tactical_layout or {}).get("meta") or {}
                meta["pdf_segment_excerpt"] = str(chunk.get("raw_text") or "")[:1200]
                task.tactical_layout = {"meta": dict(meta)}
                task.save(update_fields=["tactical_layout"])
            except Exception:
                pass
            # Adjunta preview si existe.
            payload = preview_payloads[min(idx - 1, len(preview_payloads) - 1)] if preview_payloads else None
            if payload:
                name, content = payload
                try:
                    content.seek(0)
                except Exception:
                    pass
                try:
                    task.task_preview_image.save(str(name or f"preview-{idx}.png"), content, save=True)
                except Exception:
                    pass
            created_task_ids.append(int(task.id))

        session = created_session
    else:
        if not args.session_id:
            print("ERROR: indica --session-id o --import-pdf.", file=sys.stderr)
            return 2
        session = TrainingSession.objects.select_related("microcycle__team").filter(id=args.session_id).first()
        if not session:
            print(f"ERROR: sesión no encontrada (id={args.session_id}).", file=sys.stderr)
            return 2

    rf = RequestFactory()
    req = rf.get("/", HTTP_HOST="localhost")
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    req.user = get_user_model().objects.first()
    if not req.user:
        print("ERROR: no hay usuarios en BD para simular request.", file=sys.stderr)
        return 2

    ctx = _build_session_pdf_context(req, session.microcycle.team, session, pdf_style="uefa")
    html = render_to_string("football/session_plan_pdf.html", ctx)
    pdf_bytes, pdf_error = _render_pdf_bytes_with_error(req, html)
    if not pdf_bytes:
        print(f"ERROR: no se pudo generar PDF: {pdf_error or 'desconocido'}", file=sys.stderr)
        return 3

    out_path = Path(args.out) if args.out else Path("/tmp") / f"session-{session.id}-uefa.pdf"
    out_path.write_bytes(pdf_bytes)

    ok, errors = _validate_pdf(out_path)
    if created_session and args.cleanup:
        # Limpieza de ficheros y datos temporales.
        try:
            for task_id in created_task_ids:
                task = SessionTask.objects.filter(id=task_id).first()
                if not task:
                    continue
                try:
                    if task.task_preview_image:
                        task.task_preview_image.delete(save=False)
                except Exception:
                    pass
                try:
                    if task.task_pdf:
                        task.task_pdf.delete(save=False)
                except Exception:
                    pass
                task.delete()
        except Exception:
            pass
        try:
            created_session.delete()
        except Exception:
            pass
    if ok:
        print(f"OK: PDF generado y validado: {out_path}")
        return 0
    print(f"FAIL: PDF generado pero con errores de validación: {out_path}", file=sys.stderr)
    for err in errors:
        print(f"- {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
