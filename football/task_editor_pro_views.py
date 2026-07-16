import base64
import json
import mimetypes
import os
import re
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from football.context_processors import _static_build_id

from . import permissions
from .models import SessionTask, SessionTaskExportJob
from .session_task_editor_services import (
    _ensure_original_task_snapshot,
    _forbid_if_workspace_module_disabled,
    _get_primary_team_for_request,
    _task_builder_initial_values,
)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


def _editor_task_or_404(request, task_id):
    if not permissions.can_access_sessions_workspace(request.user):
        raise Http404("No autorizado")
    forbidden = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
    if forbidden:
        return None, forbidden
    task = (
        SessionTask.objects.select_related("session__microcycle__team")
        .filter(id=task_id, deleted_at__isnull=True)
        .first()
    )
    if not task:
        raise Http404("Tarea no encontrada")
    primary_team = _get_primary_team_for_request(request)
    task_team = getattr(getattr(getattr(task, "session", None), "microcycle", None), "team", None)
    if primary_team and task_team and int(task_team.id) != int(primary_team.id):
        raise Http404("Tarea no encontrada")
    return task, None


def _editor_document_payload(request, task):
    initial = _task_builder_initial_values(task)
    try:
        canvas_state = json.loads(str(initial.get("canvas_state") or "{}"))
    except Exception:
        canvas_state = {}
    if not isinstance(canvas_state, dict):
        canvas_state = {}
    objects = canvas_state.get("objects") if isinstance(canvas_state.get("objects"), list) else []
    if not isinstance(objects, list):
        objects = []
    safe_canvas_state = dict(canvas_state)
    safe_canvas_state["objects"] = list(objects)
    if not isinstance(safe_canvas_state.get("timeline"), list):
        safe_canvas_state["timeline"] = []
    graphic_editor = ((task.tactical_layout or {}).get("meta") or {}).get("graphic_editor") or {}
    preview_name = str(getattr(getattr(task, "task_preview_image", None), "name", "") or "").strip()
    ai_meta = ((task.tactical_layout or {}).get("meta") or {}).get("ai") or {}
    ai_generated = bool(ai_meta.get("generated_preview_data_v1") or preview_name)
    ai_preview_url = reverse("session-task-ai-preview-file", args=[int(task.id)]) if ai_generated else ""
    export_jobs = []
    for job in list(task.export_jobs.order_by("-id")[:8]):
        export_jobs.append(
            {
                "id": int(job.id),
                "kind": str(job.kind or ""),
                "kind_label": dict(SessionTaskExportJob.KIND_CHOICES).get(job.kind, str(job.kind or "")),
                "status": str(job.status or ""),
                "status_label": dict(SessionTaskExportJob.STATUS_CHOICES).get(job.status, str(job.status or "")),
            }
        )
    return {
        "task": {
            "id": int(task.id),
            "title": str(task.title or ""),
            "block_label": str(task.get_block_display() or task.block or ""),
            "duration_minutes": int(task.duration_minutes or 0),
        },
        "engine": {
            "single_document": True,
            "single_3d_engine": True,
            "graphic_panels_count": 1,
            "track_count": (
                len(canvas_state.get("timeline") or []) if isinstance(canvas_state.get("timeline"), list) else 0
            ),
            "keyframe_count": (
                len(canvas_state.get("timeline") or []) if isinstance(canvas_state.get("timeline"), list) else 0
            ),
        },
        "graphic": {
            "canvas_width": int(initial.get("canvas_width") or graphic_editor.get("canvas_width") or 1280),
            "canvas_height": int(initial.get("canvas_height") or graphic_editor.get("canvas_height") or 720),
            "canvas_state": safe_canvas_state,
            "updated_at": str(graphic_editor.get("updated_at") or ""),
            "preview_2d_url": reverse("session-task-preview-file", args=[int(task.id)]),
            "preview_3d_embed_url": reverse("session-task-pdf-3d-embed", args=[int(task.id)]),
        },
        "players": {
            "total": 0,
        },
        "materials": {
            "summary": str(initial.get("materials") or ""),
        },
        "sequence": {
            "tracks": [],
            "frame_cards": [],
        },
        "exports": {
            "targets": [
                {"kind": "pdf_club", "label": "PDF Club", "state": "ready"},
                {"kind": "ai_preview", "label": "Imagen IA", "state": "ready"},
            ],
            "jobs": export_jobs,
        },
        "ai": {
            "generated": ai_generated,
            "has_analysis": True,
            "preview_url": ai_preview_url,
            "provider": str(ai_meta.get("generated_preview_provider_v1") or ""),
            "model": str(ai_meta.get("generated_preview_model_v1") or ""),
            "prompt": str(ai_meta.get("generated_preview_prompt_v1") or ""),
        },
        "urls": {
            "graphic_save": reverse("session-task-graphic-save", args=[int(task.id)]),
            "export_jobs_api": reverse("session-task-export-jobs-api", args=[int(task.id)]),
            "detail": reverse("session-task-detail", args=[int(task.id)]),
            "ai_preview": ai_preview_url,
        },
    }


def _save_ai_preview_image(task, image_bytes, provider="", model="", prompt="", mime="image/png"):
    if not image_bytes:
        return False
    extension = ".png"
    if mime == "image/jpeg":
        extension = ".jpg"
    elif mime == "image/webp":
        extension = ".webp"
    filename = f"task-{int(task.id)}-ai-preview-{os.urandom(4).hex()}{extension}"
    task.task_preview_image.save(filename, ContentFile(image_bytes), save=False)
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    meta = dict(meta)
    ai = meta.get("ai") if isinstance(meta.get("ai"), dict) else {}
    ai = dict(ai)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    ai["generated_preview_data_v1"] = f"data:{mime};base64,{encoded}"
    if provider:
        ai["generated_preview_provider_v1"] = provider
    if model:
        ai["generated_preview_model_v1"] = model
    if prompt:
        ai["generated_preview_prompt_v1"] = prompt
    meta["ai"] = ai
    layout["meta"] = meta
    task.tactical_layout = layout
    task.save(update_fields=["task_preview_image", "tactical_layout"])
    try:
        _ensure_original_task_snapshot(task)
    except Exception:
        pass
    return True


@login_required
def session_task_editor_document_api(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    return JsonResponse({"ok": True, "document": _editor_document_payload(request, task)})


@login_required
def session_task_editor_pro_page(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    payload = _editor_document_payload(request, task)
    static_build_id = str(_static_build_id() or "").strip()
    context = {
        "task": task,
        "detail_url": reverse("session-task-detail", args=[int(task.id)]),
        "builder_url": reverse("sessions-task-edit", args=[int(task.id)]),
        "editor_document_api_url": reverse("session-task-editor-document-api", args=[int(task.id)]),
        "document_payload_json": json.dumps(payload, ensure_ascii=False),
        "static_build_id": static_build_id,
    }
    return render(request, "football/session_task_editor_pro.html", context)


@login_required
def session_task_export_jobs_api(request, task_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except Exception:
        payload = {}
    raw_kind = str(payload.get("kind") or "").strip().lower()
    kind = (
        raw_kind
        if raw_kind in {choice[0] for choice in SessionTaskExportJob.KIND_CHOICES}
        else SessionTaskExportJob.KIND_PDF_CLUB
    )
    job = SessionTaskExportJob.objects.create(
        team=getattr(getattr(getattr(task, "session", None), "microcycle", None), "team"),
        task=task,
        kind=kind,
        payload=payload if isinstance(payload, dict) else {},
        status=SessionTaskExportJob.STATUS_PENDING,
        created_by=request.user.get_username() if request.user.is_authenticated else "",
        created_by_user=request.user if request.user.is_authenticated else None,
    )

    if kind == SessionTaskExportJob.KIND_AI_PREVIEW:
        image_bytes = b""
        mime = "image/png"
        provider = ""
        model = ""
        prompt = str(payload.get("prompt") or f"Vista táctica premium de {task.title}").strip()
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        image_model = str(os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip()
        if api_key and requests is not None:
            try:
                response = requests.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": image_model,
                        "size": "1024x1024",
                        "response_format": "b64_json",
                        "prompt": prompt,
                    },
                    timeout=60,
                )
                data = response.json() if hasattr(response, "json") else {}
                first = ((data.get("data") or [{}])[0] or {}) if isinstance(data, dict) else {}
                b64_json = str(first.get("b64_json") or "").strip()
                if b64_json:
                    image_bytes = base64.b64decode(b64_json.encode("ascii"), validate=False)
                    provider = "openai"
                    model = image_model
            except Exception:
                image_bytes = b""
        if not image_bytes and getattr(task, "task_preview_image", None):
            try:
                task.task_preview_image.open("rb")
                image_bytes = task.task_preview_image.read() or b""
            finally:
                try:
                    task.task_preview_image.close()
                except Exception:
                    pass
        if image_bytes:
            _save_ai_preview_image(task, image_bytes, provider=provider, model=model, prompt=prompt, mime=mime)
            job.status = SessionTaskExportJob.STATUS_DONE
            job.progress = 100
            job.message = "Imagen IA generada."
        else:
            job.status = SessionTaskExportJob.STATUS_ERROR
            job.error = "No se pudo generar la imagen de preview."
            job.message = "Preview no disponible."
        job.save(update_fields=["status", "progress", "message", "error"])
    else:
        job.status = SessionTaskExportJob.STATUS_DONE
        job.progress = 100
        job.message = "Export preparado."
        job.save(update_fields=["status", "progress", "message"])

    return JsonResponse(
        {
            "ok": job.status == SessionTaskExportJob.STATUS_DONE,
            "job_id": int(job.id),
            "status": str(job.status or ""),
        },
        status=201,
    )


@login_required
def session_task_ai_preview_file(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    if getattr(task, "task_preview_image", None):
        file_field = task.task_preview_image
        try:
            file_field.open("rb")
        except Exception:
            return HttpResponse("No se pudo abrir la imagen de la tarea.", status=500)
        content_type = mimetypes.guess_type(str(getattr(file_field, "name", "") or ""))[0] or "application/octet-stream"
        response = FileResponse(file_field, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{Path(file_field.name).name}"'
        response["Cache-Control"] = "private, max-age=0, must-revalidate"
        return response
    ai_meta = ((task.tactical_layout or {}).get("meta") or {}).get("ai") or {}
    raw_data = str(ai_meta.get("generated_preview_data_v1") or "").strip()
    if not raw_data.startswith("data:image/"):
        raise Http404("Preview no disponible")
    match = re.match(r"^data:(image/[-+.\w]+);base64,(.+)$", raw_data, re.DOTALL)
    if not match:
        raise Http404("Preview no disponible")
    mime = match.group(1)
    image_bytes = base64.b64decode(match.group(2).encode("ascii"), validate=False)
    response = HttpResponse(image_bytes, content_type=mime)
    response["Cache-Control"] = "no-store, max-age=0"
    return response
