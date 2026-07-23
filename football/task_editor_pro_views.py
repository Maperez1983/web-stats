import base64
import copy
import json
import mimetypes
import os
import re
import uuid
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from football.context_processors import _static_build_id

from . import permissions
from .models import SessionTask, SessionTaskBackup
from .session_task_editor_services import (
    _ensure_original_task_snapshot,
    _forbid_if_workspace_module_disabled,
    _get_primary_team_for_request,
    _is_local_editor_lab_request,
    _local_editor_lab_context,
    _task_builder_initial_values,
)
from .task_backups import write_task_backup

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from .models import SessionTaskExportJob
except Exception:
    class _FallbackSessionTaskExportJobManager:
        def create(self, **kwargs):
            data = dict(kwargs)
            data.setdefault("id", 0)
            data.setdefault("kind", data.get("kind", "pdf_club"))
            data.setdefault("status", "done")
            data.setdefault("progress", 100)
            data.setdefault("message", "Export preparado.")
            data.setdefault("error", "")
            return SimpleNamespace(**data)

    class SessionTaskExportJob:  # type: ignore[no-redef]
        KIND_PDF_CLUB = "pdf_club"
        KIND_AI_PREVIEW = "ai_preview"
        STATUS_PENDING = "pending"
        STATUS_DONE = "done"
        STATUS_ERROR = "error"
        KIND_CHOICES = (
            (KIND_PDF_CLUB, "PDF club"),
            (KIND_AI_PREVIEW, "Preview IA"),
        )
        STATUS_CHOICES = (
            (STATUS_PENDING, "Pendiente"),
            (STATUS_DONE, "Hecho"),
            (STATUS_ERROR, "Error"),
        )
        objects = _FallbackSessionTaskExportJobManager()


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
    export_jobs_manager = getattr(task, "export_jobs", None)
    try:
        export_jobs_iter = list(export_jobs_manager.order_by("-id")[:8]) if export_jobs_manager is not None else []
    except Exception:
        export_jobs_iter = []
    for job in export_jobs_iter:
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
            "save_as": reverse("session-task-editor-save-as-api", args=[int(task.id)]),
            "duplicate": reverse("session-task-editor-save-as-api", args=[int(task.id)]),
            "rename": reverse("session-task-editor-rename-api", args=[int(task.id)]),
            "delete": reverse("session-task-editor-delete-api", args=[int(task.id)]),
            "versions": reverse("session-task-editor-versions-api", args=[int(task.id)]),
            "restore_version": reverse("session-task-editor-restore-version-api", args=[int(task.id)]),
            "export_jobs_api": reverse("session-task-export-jobs-api", args=[int(task.id)]),
            "detail": reverse("session-task-detail", args=[int(task.id)]),
            "ai_preview": ai_preview_url,
        },
    }


def _decode_canvas_preview_data(raw_preview: str):
    text = str(raw_preview or "").strip()
    if not text:
        return b"", ""
    match = re.match(r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", text, flags=re.I | re.S)
    if not match:
        return b"", ""
    mime = str(match.group(1) or "image/png").strip().lower()
    encoded = str(match.group(2) or "").strip()
    if not encoded:
        return b"", ""
    try:
        raw_bytes = base64.b64decode(encoded.encode("ascii"), validate=False)
    except Exception:
        return b"", ""
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }.get(mime, ".png")
    return raw_bytes, extension


def _apply_graphic_payload_to_task(task, payload, *, keep_preview=True):
    if not task or not isinstance(payload, dict):
        return []
    canvas_state = payload.get("canvas_state")
    if not isinstance(canvas_state, dict):
        canvas_state = {}
    canvas_width = int(payload.get("canvas_width") or 0)
    canvas_height = int(payload.get("canvas_height") or 0)
    preview_data = str(payload.get("preview_data") or "").strip()
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    meta = dict(meta)
    graphic_editor = meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {}
    graphic_editor = dict(graphic_editor)
    graphic_editor.update(
        {
            "canvas_state": canvas_state,
            "canvas_width": canvas_width if canvas_width and canvas_width > 0 else None,
            "canvas_height": canvas_height if canvas_height and canvas_height > 0 else None,
            "updated_at": timezone.now().isoformat(),
        }
    )
    meta["graphic_editor"] = graphic_editor
    layout["meta"] = meta
    task.tactical_layout = layout
    update_fields = ["tactical_layout"]

    if keep_preview and preview_data:
        raw_bytes, extension = _decode_canvas_preview_data(preview_data)
        if raw_bytes and extension:
            filename = f"task-{int(task.id)}-graphic-{uuid.uuid4().hex[:10]}{extension}"
            task.task_preview_image.save(filename, ContentFile(raw_bytes), save=False)
            update_fields.append("task_preview_image")
            try:
                embedded = f'data:image/{extension.lstrip(".")};base64,{base64.b64encode(raw_bytes).decode("ascii")}'
                if embedded:
                    meta["preview_data_embedded_v1"] = embedded
                    layout["meta"] = meta
                    task.tactical_layout = layout
                    if "tactical_layout" not in update_fields:
                        update_fields.append("tactical_layout")
            except Exception:
                pass

    task.save(update_fields=update_fields)
    return update_fields


def _clone_task_for_save_as(source_task, *, title: str = "", payload=None, actor_username: str = ""):
    cloned = SessionTask.objects.create(
        session=source_task.session,
        title=str(title or "").strip()[:160] or f"{str(source_task.title or 'Tarea').strip() or 'Tarea'} (copia)",
        block=source_task.block,
        duration_minutes=source_task.duration_minutes,
        objective=source_task.objective,
        coaching_points=source_task.coaching_points,
        confrontation_rules=source_task.confrontation_rules,
        notes=source_task.notes,
        status=SessionTask.STATUS_PLANNED,
        order=0,
        tactical_layout=(
            copy.deepcopy(source_task.tactical_layout) if isinstance(source_task.tactical_layout, dict) else {}
        ),
        task_pdf=source_task.task_pdf.name if source_task.task_pdf else None,
        task_preview_image=source_task.task_preview_image.name if source_task.task_preview_image else None,
    )
    try:
        layout = cloned.tactical_layout if isinstance(cloned.tactical_layout, dict) else {}
        layout = copy.deepcopy(layout) if isinstance(layout, dict) else {}
        meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
        meta = dict(meta) if isinstance(meta, dict) else {}
        meta.pop("original_version", None)
        layout["meta"] = meta
        cloned.tactical_layout = layout
        update_fields = ["tactical_layout"]
        if payload:
            update_fields = list(_apply_graphic_payload_to_task(cloned, payload))
        else:
            cloned.save(update_fields=update_fields)
    except Exception:
        cloned.save()
    try:
        write_task_backup(cloned, kind="session_task", reason="save_as", actor_username=actor_username)
    except Exception:
        pass
    return cloned


def _serialize_task_version_backup(backup):
    payload = getattr(backup, "payload", None) if backup else None
    task_data = payload.get("task") if isinstance(payload, dict) else {}
    if not isinstance(task_data, dict):
        task_data = {}
    layout = task_data.get("tactical_layout") if isinstance(task_data.get("tactical_layout"), dict) else {}
    graphic = layout.get("meta", {}).get("graphic_editor", {}) if isinstance(layout.get("meta"), dict) else {}
    canvas_state = graphic.get("canvas_state") if isinstance(graphic.get("canvas_state"), dict) else {}
    return {
        "id": int(getattr(backup, "id", 0) or 0),
        "captured_at": str(getattr(backup, "created_at", "") or ""),
        "reason": str(getattr(backup, "reason", "") or ""),
        "actor": str(getattr(backup, "actor_username", "") or ""),
        "kind": str(getattr(backup, "kind", "") or ""),
        "title": str(task_data.get("title") or ""),
        "block": str(task_data.get("block") or ""),
        "duration_minutes": int(task_data.get("duration_minutes") or 0),
        "objects_count": len(canvas_state.get("objects") or []) if isinstance(canvas_state.get("objects"), list) else 0,
        "timeline_count": (
            len(canvas_state.get("timeline") or []) if isinstance(canvas_state.get("timeline"), list) else 0
        ),
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
    # El editor-pro (Konva/React) no tiene frontend construido en producción
    # (falta football/static/football/editor-pro/tactical-editor.js), y con
    # manifest estricto el {% static %} reventaba en 500. Hasta que exista el
    # build, redirigimos al editor 2D operativo (Fabric).
    return redirect(reverse("sessions-task-edit", args=[int(task.id)]))


@login_required
def session_task_editor_lab_compare_page(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not _is_local_editor_lab_request(request):
        return HttpResponse("No disponible.", status=404)
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    task_payload = _editor_document_payload(request, task)
    task_id_int = int(task.id)
    context = {
        "task": task,
        "static_build_id": str(_static_build_id() or "").strip(),
        "production_url": f"{reverse('sessions-task-edit', args=[task_id_int])}?editor_lab=production&editor_lab_compare=1&editor_lab_compare_side=production",
        "konva_url": f"{reverse('session-task-editor-pro', args=[task_id_int])}?editor_lab=konva&editor_lab_compare=1&editor_lab_compare_side=konva",
        "detail_url": reverse("session-task-detail", args=[task_id_int]),
        "builder_url": reverse("sessions-task-edit", args=[task_id_int]),
        "document_payload_json": json.dumps(task_payload, ensure_ascii=False),
        **_local_editor_lab_context(request, task, current_mode="comparison"),
    }
    return render(request, "football/session_task_editor_lab_compare.html", context)


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
    job_is_persistent = bool(getattr(job, "save", None))

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
        if job_is_persistent:
            job.save(update_fields=["status", "progress", "message", "error"])
    else:
        job.status = SessionTaskExportJob.STATUS_DONE
        job.progress = 100
        job.message = "Export preparado."
        if job_is_persistent:
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
@require_POST
def session_task_editor_save_as_api(request, task_id):
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    raw_title = str(payload.get("title") or "").strip()
    cloned = _clone_task_for_save_as(
        task,
        title=raw_title,
        payload=payload,
        actor_username=(request.user.get_username() if request.user.is_authenticated else ""),
    )
    return JsonResponse(
        {
            "ok": True,
            "task": {
                "id": int(cloned.id),
                "title": str(cloned.title or ""),
            },
            "detail_url": reverse("session-task-detail", args=[int(cloned.id)]),
            "editor_url": reverse("session-task-editor-pro", args=[int(cloned.id)]),
        }
    )


@login_required
@require_POST
def session_task_editor_rename_api(request, task_id):
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    title = str(payload.get("title") or "").strip()
    if not title:
        return JsonResponse({"ok": False, "error": "Título requerido."}, status=400)
    task.title = title[:160]
    task.save(update_fields=["title"])
    try:
        write_task_backup(
            task,
            kind="session_task",
            reason="rename",
            actor_username=(request.user.get_username() if request.user.is_authenticated else ""),
        )
    except Exception:
        pass
    return JsonResponse(
        {
            "ok": True,
            "task": {
                "id": int(task.id),
                "title": str(task.title or ""),
            },
            "document": _editor_document_payload(request, task),
        }
    )


@login_required
@require_POST
def session_task_editor_delete_api(request, task_id):
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    task.deleted_at = timezone.now()
    if hasattr(task, "deleted_by"):
        task.deleted_by = request.user if request.user.is_authenticated else None
    update_fields = ["deleted_at"]
    if hasattr(task, "deleted_by"):
        update_fields.append("deleted_by")
    task.save(update_fields=update_fields)
    try:
        write_task_backup(
            task,
            kind="session_task",
            reason="delete",
            actor_username=(request.user.get_username() if request.user.is_authenticated else ""),
        )
    except Exception:
        pass
    return JsonResponse({"ok": True, "redirect_url": reverse("sessions")})


@login_required
def session_task_editor_versions_api(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    team = getattr(getattr(getattr(task, "session", None), "microcycle", None), "team", None)
    backups = (
        SessionTaskBackup.objects.filter(team=team, task_id=int(task.id)).order_by("-created_at", "-id")[:20]
        if team
        else []
    )
    return JsonResponse({"ok": True, "versions": [_serialize_task_version_backup(backup) for backup in backups]})


@login_required
@require_POST
def session_task_editor_restore_version_api(request, task_id):
    task, forbidden = _editor_task_or_404(request, task_id)
    if forbidden:
        return forbidden
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    backup_id = int(payload.get("backup_id") or 0)
    if backup_id <= 0:
        return JsonResponse({"ok": False, "error": "backup_id requerido."}, status=400)
    team = getattr(getattr(getattr(task, "session", None), "microcycle", None), "team", None)
    backup = SessionTaskBackup.objects.filter(id=backup_id, task_id=int(task.id), team=team).first() if team else None
    if not backup or not isinstance(getattr(backup, "payload", None), dict):
        return JsonResponse({"ok": False, "error": "Versión no encontrada."}, status=404)
    task_data = backup.payload.get("task") if isinstance(backup.payload, dict) else {}
    if not isinstance(task_data, dict):
        return JsonResponse({"ok": False, "error": "Versión no válida."}, status=400)

    task.title = str(task_data.get("title") or task.title or "")[:160]
    task.block = str(task_data.get("block") or task.block or "")[:30] or task.block
    task.duration_minutes = max(1, min(240, int(task_data.get("duration_minutes") or task.duration_minutes or 15)))
    task.objective = str(task_data.get("objective") or "")
    task.coaching_points = str(task_data.get("coaching_points") or "")
    task.confrontation_rules = str(task_data.get("confrontation_rules") or "")
    task.notes = str(task_data.get("notes") or "")
    task.tactical_layout = (
        copy.deepcopy(task_data.get("tactical_layout")) if isinstance(task_data.get("tactical_layout"), dict) else {}
    )
    update_fields = [
        "title",
        "block",
        "duration_minutes",
        "objective",
        "coaching_points",
        "confrontation_rules",
        "notes",
        "tactical_layout",
    ]
    try:
        pdf_name = str(task_data.get("task_pdf") or "").strip()
        if pdf_name:
            task.task_pdf.name = pdf_name
            update_fields.append("task_pdf")
        img_name = str(task_data.get("task_preview_image") or "").strip()
        if img_name:
            task.task_preview_image.name = img_name
            update_fields.append("task_preview_image")
    except Exception:
        pass
    task.save(update_fields=sorted(set(update_fields)))
    try:
        write_task_backup(
            task,
            kind="session_task",
            reason="restore_version",
            actor_username=(request.user.get_username() if request.user.is_authenticated else ""),
        )
    except Exception:
        pass
    return JsonResponse({"ok": True, "document": _editor_document_payload(request, task)})


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
