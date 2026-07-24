"""Servicios compartidos del editor profesional de tareas."""

import json
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from . import permissions, task_library_services, workspace_context, workspace_subscription
from .drills import normalize_drill_ids
from .models import (
    AppUserRole,
    SessionTask,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)
from .services import _parse_int


def _paywall_response(request, *, workspace=None):
    try:
        url = reverse("billing")
        if workspace and getattr(workspace, "id", None):
            url = f"{url}?workspace={workspace.id}"
    except Exception:
        url = "/billing/"
    return HttpResponse(
        f"Periodo de prueba finalizado. Activa la suscripción para continuar. {url}",
        status=402,
    )


def _workspace_needs_setup(workspace) -> bool:
    if not workspace or getattr(workspace, "kind", None) != Workspace.KIND_CLUB:
        return False
    if getattr(workspace, "primary_team_id", None):
        return False
    return not WorkspaceTeam.objects.filter(workspace=workspace).exists()


def _is_local_editor_lab_request(request) -> bool:
    if not request or not getattr(request, "META", None):
        return False
    try:
        if not bool(getattr(settings, "DEBUG", False)):
            return False
    except Exception:
        return False
    host = str(getattr(request, "get_host", lambda: "")() or "").split(":", 1)[0].strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _find_local_editor_lab_task(request):
    if not _is_local_editor_lab_request(request):
        return None
    _ensure_local_editor_lab_workspace(request)
    primary_team = _get_primary_team_for_request(request)
    if not primary_team:
        return None
    task = (
        SessionTask.objects.select_related("session__microcycle__team")
        .filter(
            session__microcycle__team=primary_team,
            deleted_at__isnull=True,
            title__iexact="Local Editor Lab Task",
        )
        .order_by("session__session_date", "session__order", "order", "id")
        .first()
    )
    if task:
        return task

    task = (
        SessionTask.objects.select_related("session__microcycle__team")
        .filter(
            session__microcycle__team=primary_team,
            deleted_at__isnull=True,
            title__iexact="Laboratorio local · Editor",
        )
        .order_by("session__session_date", "session__order", "order", "id")
        .first()
    )
    if task:
        return task

    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    microcycle, _ = TrainingMicrocycle.objects.get_or_create(
        team=primary_team,
        week_start=monday,
        defaults={
            "week_end": sunday,
            "title": "Laboratorio local",
            "objective": "Entorno local estable para editar tareas.",
        },
    )
    session, _ = TrainingSession.objects.get_or_create(
        microcycle=microcycle,
        session_date=today,
        defaults={
            "duration_minutes": 90,
            "focus": "Laboratorio local",
            "status": TrainingSession.STATUS_PLANNED,
        },
    )
    task, _ = SessionTask.objects.get_or_create(
        session=session,
        title="Local Editor Lab Task",
        defaults={
            "block": SessionTask.BLOCK_MAIN_1,
            "duration_minutes": 18,
            "objective": "Editor de producción local para validar cambios sin tocar producción.",
            "coaching_points": "Tarea estable del laboratorio local.",
            "confrontation_rules": "",
            "notes": "Generada automáticamente para el laboratorio local.",
            "status": SessionTask.STATUS_PLANNED,
            "order": 0,
            "tactical_layout": {
                "meta": {
                    "local_lab": True,
                    "graphic_editor": {
                        "canvas_state": {
                            "version": "5.3.0",
                            "objects": [],
                            "timeline": [],
                        },
                        "canvas_width": 1280,
                        "canvas_height": 720,
                    },
                }
            },
        },
    )
    if not isinstance(task.tactical_layout, dict):
        task.tactical_layout = {}
    layout = dict(task.tactical_layout)
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    meta = dict(meta)
    meta["local_lab"] = True
    graphic = meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {}
    graphic = dict(graphic)
    if not isinstance(graphic.get("canvas_state"), dict):
        graphic["canvas_state"] = {
            "version": "5.3.0",
            "objects": [],
            "timeline": [],
        }
    graphic.setdefault("canvas_width", 1280)
    graphic.setdefault("canvas_height", 720)
    meta["graphic_editor"] = graphic
    layout["meta"] = meta
    task.tactical_layout = layout
    task.save(update_fields=["tactical_layout"])
    return task


def _ensure_local_editor_lab_workspace(request):
    if not _is_local_editor_lab_request(request):
        return None
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    team = _get_primary_team_for_request(request)
    workspace = workspace_context.get_active_workspace(request)
    if team and workspace:
        return workspace
    team = (
        Team.objects.filter(slug="local-editor-lab-team").first()
        or Team.objects.filter(name__iexact="Laboratorio local").first()
    )
    if not team:
        team = Team.objects.create(
            name="Laboratorio local",
            slug="local-editor-lab-team",
            short_name="Lab",
            is_primary=True,
        )
    else:
        changed = []
        if not getattr(team, "is_primary", False):
            team.is_primary = True
            changed.append("is_primary")
        if changed:
            team.save(update_fields=changed)
    workspace = (
        Workspace.objects.filter(primary_team=team).first()
        or Workspace.objects.filter(slug="local-editor-lab-workspace").first()
        or Workspace.objects.filter(slug="local-editor-lab").first()
        or Workspace.objects.filter(name__iexact="Local Editor Lab Workspace").first()
        or Workspace.objects.filter(name__iexact="Laboratorio local").first()
    )
    workspace_created = False
    if not workspace:
        workspace = Workspace.objects.create(
            name="Laboratorio local",
            slug="local-editor-lab-workspace",
        )
        workspace_created = True
    changed = []
    if workspace_created and getattr(workspace, "name", "") != "Laboratorio local":
        workspace.name = "Laboratorio local"
        changed.append("name")
    if workspace_created and getattr(workspace, "slug", "") != "local-editor-lab-workspace":
        workspace.slug = "local-editor-lab-workspace"
        changed.append("slug")
    if hasattr(workspace, "kind") and getattr(workspace, "kind", None) != Workspace.KIND_CLUB:
        workspace.kind = Workspace.KIND_CLUB
        changed.append("kind")
    if hasattr(workspace, "primary_team_id") and getattr(workspace, "primary_team_id", None) != getattr(
        team, "id", None
    ):
        workspace.primary_team = team
        changed.append("primary_team")
    if hasattr(workspace, "owner_user_id") and getattr(workspace, "owner_user_id", None) != getattr(user, "id", None):
        workspace.owner_user = user
        changed.append("owner_user")
    if hasattr(workspace, "is_active") and not getattr(workspace, "is_active", True):
        workspace.is_active = True
        changed.append("is_active")
    if hasattr(workspace, "enabled_modules"):
        enabled_modules = getattr(workspace, "enabled_modules", None)
        if not isinstance(enabled_modules, dict) or not enabled_modules.get("sessions"):
            workspace.enabled_modules = {"sessions": True}
            changed.append("enabled_modules")
    if changed:
        workspace.save(update_fields=changed)
    WorkspaceMembership.objects.update_or_create(
        workspace=workspace,
        user=user,
        defaults={
            "role": WorkspaceMembership.ROLE_OWNER,
            "module_access": {"sessions": True},
        },
    )
    WorkspaceTeam.objects.update_or_create(
        workspace=workspace,
        team=team,
        defaults={"is_default": True},
    )
    try:
        session = getattr(request, "session", None)
        if session is not None:
            session["active_workspace_id"] = int(workspace.id)
            mapping = session.get("active_team_by_workspace")
            if not isinstance(mapping, dict):
                mapping = {}
            mapping[str(workspace.id)] = int(team.id)
            session["active_team_by_workspace"] = mapping
    except Exception:
        pass
    return workspace


def _local_editor_lab_context(request, task, *, current_mode: str = "production") -> dict:
    mode = str(current_mode or "production").strip().lower()
    if mode not in {"production", "konva", "comparison"}:
        mode = "production"
    task_id = int(getattr(task, "id", 0) or 0)
    enabled = bool(task_id) and _is_local_editor_lab_request(request)
    if not enabled:
        return {
            "local_editor_lab_enabled": False,
            "local_editor_lab_mode": mode,
            "local_editor_lab_task_id": task_id,
            "local_editor_lab_production_url": "",
            "local_editor_lab_konva_url": "",
            "local_editor_lab_comparison_url": "",
        }
    embedded_suffix = "&embedded=1"
    return {
        "local_editor_lab_enabled": True,
        "local_editor_lab_mode": mode,
        "local_editor_lab_task_id": task_id,
        "local_editor_lab_production_url": f"{reverse('sessions-task-edit', args=[task_id])}?editor_lab=production{embedded_suffix}",
        "local_editor_lab_konva_url": f"{reverse('session-task-editor-pro', args=[task_id])}?editor_lab=konva{embedded_suffix}",
        "local_editor_lab_comparison_url": f"{reverse('session-task-editor-lab-compare', args=[task_id])}?editor_lab=comparison{embedded_suffix}",
    }


def _ensure_original_task_snapshot(task):
    if not task:
        return {}
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    meta = dict(meta)
    if isinstance(meta.get("original_version"), dict):
        return meta.get("original_version") or {}
    analysis_meta = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else {}
    analysis_meta = dict(analysis_meta)
    task_sheet = analysis_meta.get("task_sheet") if isinstance(analysis_meta.get("task_sheet"), dict) else {}
    snapshot = {
        "captured_at": timezone.now().isoformat(),
        "title": task.title or "",
        "block": task.block or "",
        "duration_minutes": int(task.duration_minutes or 0),
        "objective": task.objective or "",
        "coaching_points": task.coaching_points or "",
        "confrontation_rules": task.confrontation_rules or "",
        "task_sheet": dict(task_sheet),
        "graphic_editor": meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {},
        "task_preview_image": task.task_preview_image.name if task.task_preview_image else "",
        "task_pdf": task.task_pdf.name if task.task_pdf else "",
    }
    meta["original_version"] = snapshot
    layout["meta"] = meta
    task.tactical_layout = layout
    task.save(update_fields=["tactical_layout"])
    return snapshot


def _get_primary_team_for_request(request):
    team = workspace_context.get_active_team_for_request(request)
    if team:
        return team
    try:
        team = workspace_context.team_from_request_param(request)
        if team:
            return team
    except Exception:
        pass
    if request and getattr(request, "user", None) and request.user.is_authenticated:
        try:
            link = (
                WorkspaceTeam.objects.select_related("workspace", "team")
                .filter(
                    workspace__in=workspace_context.available_workspaces_for_user(request.user),
                    workspace__kind=Workspace.KIND_CLUB,
                    workspace__is_active=True,
                )
                .order_by("-is_default", "workspace__id", "team__name", "id")
                .first()
            )
        except Exception:
            link = None
        if link and getattr(link, "team", None):
            try:
                if hasattr(request, "session"):
                    request.session["active_workspace_id"] = int(link.workspace_id)
                    mapping = request.session.get("active_team_by_workspace")
                    if not isinstance(mapping, dict):
                        mapping = {}
                    mapping[str(link.workspace_id)] = int(link.team_id)
                    request.session["active_team_by_workspace"] = mapping
            except Exception:
                pass
            return link.team
    return None


def _forbid_if_workspace_module_disabled(request, module_key, label="módulo"):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace:
        if (
            request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not workspace_context.can_access_platform(request.user)
        ):
            role = workspace_context.get_user_role(request.user)
            if role == AppUserRole.ROLE_PLAYER:
                if module_key in {"players", "dashboard"}:
                    return None
                return HttpResponse("No tienes un workspace de club asignado.", status=403)
            return None
        return None
    try:
        if (
            request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not workspace_context.can_access_platform(request.user)
            and module_key not in {"dashboard", "billing"}
            and workspace_subscription.requires_subscription(workspace)
        ):
            try:
                accept = str(request.META.get("HTTP_ACCEPT") or "")
            except Exception:
                accept = ""
            if request.method == "GET" and "text/html" in accept:
                try:
                    billing_url = reverse("billing")
                    return redirect(f'{billing_url}?next={quote(request.get_full_path() or "/")}')
                except Exception:
                    return redirect("/billing/")
            return _paywall_response(request, workspace=workspace)
    except Exception:
        pass
    if workspace.kind != Workspace.KIND_CLUB:
        if (
            request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not workspace_context.can_access_platform(request.user)
        ):
            role = workspace_context.get_user_role(request.user)
            if role == AppUserRole.ROLE_PLAYER:
                if module_key in {"players", "dashboard"}:
                    return None
                return HttpResponse("El workspace activo no es de tipo club.", status=403)
            return None
        return None
    try:
        if (
            request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not workspace_context.can_access_platform(request.user)
            and module_key not in {"dashboard", "billing"}
        ):
            status = str(getattr(workspace, "subscription_status", "") or "").strip().lower()
            if status == "active":
                paid = getattr(workspace, "paid_modules", None)
                if isinstance(paid, dict) and paid:
                    if not permissions.workspace_has_module_for_user(
                        workspace, module_key, user=getattr(request, "user", None)
                    ):
                        try:
                            accept = str(request.META.get("HTTP_ACCEPT") or "")
                        except Exception:
                            accept = ""
                        if request.method == "GET" and "text/html" in accept:
                            try:
                                billing_url = reverse("billing")
                                return redirect(f"{billing_url}?need={quote(module_key)}")
                            except Exception:
                                return redirect("/billing/")
                        return HttpResponse(
                            "Este módulo no está incluido en tu suscripción. Ve a /billing/ para activarlo.", status=402
                        )
    except Exception:
        pass
    try:
        if (
            module_key != "dashboard"
            and _workspace_needs_setup(workspace)
            and request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not workspace_context.can_access_platform(request.user)
        ):
            return HttpResponse(
                "Este club todavía no tiene equipo/configuración. Completa el onboarding primero.", status=403
            )
    except Exception:
        pass
    if permissions.workspace_has_module_for_user(workspace, module_key, user=request.user if request else None):
        return None
    return HttpResponse(f"El {label} no está activo en el workspace actual.", status=403)


def _task_builder_initial_values(task):
    layout = {}
    meta = {}
    timeline = []
    if task:
        try:
            layout = getattr(task, "tactical_layout", None)
        except Exception:
            layout = None
        if isinstance(layout, str):
            layout = task_library_services.coerce_json_dict(layout) or {}
        if not isinstance(layout, dict):
            layout = {}
        meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    timeline = layout.get("timeline") if isinstance(layout.get("timeline"), list) else []
    meta = meta if isinstance(meta, dict) else {}
    analysis = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else {}
    task_sheet = analysis.get("task_sheet") if isinstance(analysis.get("task_sheet"), dict) else {}
    graphic_editor = meta.get("graphic_editor")
    if isinstance(graphic_editor, str):
        graphic_editor = task_library_services.coerce_json_dict(graphic_editor) or {}
    if not isinstance(graphic_editor, dict):
        graphic_editor = {}
    canvas_state = (
        task_library_services.coerce_json_dict(graphic_editor.get("canvas_state"))
        or graphic_editor.get("canvas_state")
        or None
    )
    fallback_canvas_size = None

    def _coerce_timeline_frames(raw):
        if not isinstance(raw, list):
            return []
        out = []
        for index, frame in enumerate(raw[:24]):
            if not isinstance(frame, dict):
                continue
            state = frame.get("canvas_state")
            if isinstance(state, str):
                state = task_library_services.coerce_json_dict(state)
            if not isinstance(state, dict):
                continue
            out.append(
                {
                    "title": str(frame.get("title") or f"Paso {index + 1}"),
                    "duration": int(_parse_int(frame.get("duration")) or 3),
                    "canvas_state": state,
                    "canvas_width": int(_parse_int(frame.get("canvas_width")) or 0),
                    "canvas_height": int(_parse_int(frame.get("canvas_height")) or 0),
                }
            )
        return out

    timeline = _coerce_timeline_frames(timeline)

    def _build_preview_background_state(task_obj, *, portrait: bool) -> dict:
        if not task_obj:
            return {}
        preview_src = ""
        try:
            raw_layout = getattr(task_obj, "tactical_layout", None)
            if isinstance(raw_layout, str):
                raw_layout = task_library_services.coerce_json_dict(raw_layout) or {}
            if not isinstance(raw_layout, dict):
                raw_layout = {}
            raw_meta = raw_layout.get("meta") if isinstance(raw_layout.get("meta"), dict) else {}
            embedded = str(raw_meta.get("preview_data_embedded_v1") or "").strip()
            if embedded.startswith("data:image/"):
                preview_src = embedded
        except Exception:
            preview_src = ""
        if not preview_src:
            try:
                preview_name = str(getattr(getattr(task_obj, "task_preview_image", None), "name", "") or "").strip()
            except Exception:
                preview_name = ""
            v = quote(preview_name) if preview_name else str(int(getattr(task_obj, "id", 0) or 0))
            preview_src = f'/coach/sesiones/tarea/{int(getattr(task_obj, "id", 0) or 0)}/preview/?hd=1&v={v}'
        world_w = 684 if portrait else 1054
        world_h = 1054 if portrait else 684
        return {
            "version": "5.3.0",
            "objects": [
                {
                    "type": "image",
                    "left": int(round(world_w / 2)),
                    "top": int(round(world_h / 2)),
                    "originX": "center",
                    "originY": "center",
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "angle": 0,
                    "opacity": 1,
                    "src": preview_src,
                    "selectable": True,
                    "evented": True,
                    "hasControls": False,
                    "hasBorders": False,
                    "objectCaching": False,
                    "data": {
                        "kind": "preview-background",
                        "locked": True,
                        "source": "task_preview",
                    },
                }
            ],
        }

    def _state_objects_count(state):
        try:
            objs = state.get("objects") if isinstance(state, dict) else None
            return len(objs) if isinstance(objs, list) else 0
        except Exception:
            return 0

    if (
        (not isinstance(canvas_state, dict) or _state_objects_count(canvas_state) == 0)
        and task
        and isinstance(layout, dict)
    ):
        tokens = layout.get("tokens")
        if isinstance(tokens, list) and tokens:
            looks_like_fabric = False
            try:
                sample = next((item for item in tokens if isinstance(item, dict)), None)
                looks_like_fabric = bool(
                    sample
                    and (
                        sample.get("type")
                        or sample.get("objects")
                        or sample.get("_objects")
                        or sample.get("left") is not None
                    )
                )
            except Exception:
                looks_like_fabric = False
            if looks_like_fabric:
                canvas_state = {"version": "5.3.0", "objects": tokens}
                orientation = str(meta.get("pitch_orientation") or "landscape").strip().lower()
                fallback_canvas_size = (684, 1054) if orientation == "portrait" else (1054, 684)

    if (
        (not isinstance(canvas_state, dict) or _state_objects_count(canvas_state) == 0)
        and task
        and getattr(task, "task_preview_image", None)
    ):
        orientation = str(meta.get("pitch_orientation") or "landscape").strip().lower()
        portrait = orientation == "portrait"
        canvas_state = _build_preview_background_state(task, portrait=portrait)
        fallback_canvas_size = (684, 1054) if portrait else (1054, 684)

    if not isinstance(canvas_state, dict):
        canvas_state = {"version": "5.3.0", "objects": []}
    canvas_state = dict(canvas_state)
    if isinstance(timeline, list) and timeline:
        canvas_state["timeline"] = timeline
        canvas_state["active_step_index"] = 0
    drills_ids = normalize_drill_ids(meta.get("drills"))
    canvas_width = int(graphic_editor.get("canvas_width") or 0) or (
        fallback_canvas_size[0] if fallback_canvas_size else 1280
    )
    canvas_height = int(graphic_editor.get("canvas_height") or 0) or (
        fallback_canvas_size[1] if fallback_canvas_size else 720
    )
    return {
        "multi_board_enabled": bool(meta.get("multi_board") or meta.get("multi_board_enabled") or False),
        "target_session_id": str(getattr(task, "session_id", "") or ""),
        "title": str(getattr(task, "title", "") or ""),
        "block": str(getattr(task, "block", "") or SessionTask.BLOCK_MAIN_1),
        "minutes": int(getattr(task, "duration_minutes", 15) or 15),
        "objective": str(getattr(task, "objective", "") or ""),
        "coaching_points": str(getattr(task, "coaching_points", "") or ""),
        "confrontation_rules": str(getattr(task, "confrontation_rules", "") or ""),
        "description": str(task_sheet.get("description") or ""),
        "description_html": str(task_sheet.get("description_html") or ""),
        "coaching_points_html": str(task_sheet.get("coaching_html") or ""),
        "confrontation_rules_html": str(task_sheet.get("rules_html") or ""),
        "players": str(task_sheet.get("players") or ""),
        "materials": str(task_sheet.get("materials") or ""),
        "dimensions": str(task_sheet.get("dimensions") or ""),
        "space": str(meta.get("space") or task_sheet.get("space") or ""),
        "organization": str(meta.get("organization") or ""),
        "organization_html": str(meta.get("organization_html") or ""),
        "work_rest": str(meta.get("work_rest") or ""),
        "load_target": str(meta.get("load_target") or ""),
        "players_distribution": str(meta.get("players_distribution") or ""),
        "progression": str(meta.get("progression") or ""),
        "progression_html": str(meta.get("progression_html") or ""),
        "regression": str(meta.get("regression") or ""),
        "regression_html": str(meta.get("regression_html") or ""),
        "success_criteria": str(meta.get("success_criteria") or ""),
        "success_criteria_html": str(meta.get("success_criteria_html") or ""),
        "surface": str(meta.get("surface") or ""),
        "pitch_format": str(meta.get("pitch_format") or ""),
        "game_phase": str(meta.get("game_phase") or ""),
        "game_moment": str(meta.get("game_moment") or ""),
        "principle": str(meta.get("principle") or ""),
        "subprinciple": str(meta.get("subprinciple") or ""),
        "provocation_rule": str(meta.get("provocation_rule") or ""),
        "dominant_structure": str(meta.get("dominant_structure") or ""),
        "secondary_structure": str(meta.get("secondary_structure") or ""),
        "physical_load": str(meta.get("physical_load") or ""),
        "cognitive_load": str(meta.get("cognitive_load") or ""),
        "emotional_load": str(meta.get("emotional_load") or ""),
        "rpe_scale": str(meta.get("rpe_scale") or "cr10"),
        "planned_rpe": "" if meta.get("planned_rpe") is None else str(meta.get("planned_rpe") or ""),
        "planned_srpe_load": "" if meta.get("planned_srpe_load") is None else str(meta.get("planned_srpe_load") or ""),
        "wellness_target": "" if meta.get("wellness_target") is None else str(meta.get("wellness_target") or ""),
        "monotony_target": str(meta.get("monotony_target") or ""),
        "strain_target": str(meta.get("strain_target") or ""),
        "md_day": str(meta.get("md_day") or ""),
        "dominant_load": str(meta.get("dominant_load") or ""),
        "load_notes": str(meta.get("load_notes") or ""),
        "methodology": str(meta.get("methodology") or ""),
        "complexity": str(meta.get("complexity") or ""),
        "strategy": str(meta.get("strategy") or ""),
        "coordination": str(meta.get("coordination") or ""),
        "coordination_skills": str(meta.get("coordination_skills") or ""),
        "tactical_intent": str(meta.get("tactical_intent") or ""),
        "dynamics": str(meta.get("dynamics") or ""),
        "structure": str(meta.get("structure") or ""),
        "template_key": str(meta.get("template_key") or "none"),
        "pitch_preset": str(meta.get("pitch_preset") or "full_pitch"),
        "pitch_orientation": str(meta.get("pitch_orientation") or "landscape"),
        "pitch_zoom": str(meta.get("pitch_zoom") or "1.00"),
        "pitch_grass_style": (
            # Tarea nueva (sin superficie guardada) → 2D cenital plano, sin estética de estadio 3D.
            "flat_2d"
            if not str(meta.get("pitch_grass_style") or "").strip()
            # Compatibilidad: tareas guardadas con variantes "top" mantienen el estadio.
            else "stadium_native"
            if str(meta.get("pitch_grass_style") or "").strip().lower()
            in {"stadium_top", "stadium_top_h", "stadium_top_v"}
            else str(meta.get("pitch_grass_style") or "flat_2d")
        ),
        "series": str(meta.get("series") or ""),
        "repetitions": str(meta.get("repetitions") or ""),
        "player_count": str(meta.get("player_count") or ""),
        "age_group": str(meta.get("age_group") or ""),
        "training_type": str(meta.get("training_type") or ""),
        "category_tags": (
            ", ".join(meta.get("category_tags") or [])
            if isinstance(meta.get("category_tags"), list)
            else str(meta.get("category_tags") or "")
        ),
        "assigned_player_ids": [int(value) for value in (meta.get("assigned_player_ids") or []) if _parse_int(value)],
        "constraints": [str(value) for value in (meta.get("constraints") or []) if str(value).strip()],
        "canvas_state": json.dumps(canvas_state, ensure_ascii=False),
        "canvas_width": canvas_width,
        "canvas_height": canvas_height,
        "drills_ids": drills_ids,
        "drills_json": json.dumps(drills_ids, ensure_ascii=False),
        "drills_icon_color": str(meta.get("drills_icon_color") or "#0f7a35"),
    }
