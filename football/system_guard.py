from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone as django_timezone

from football.healthchecks import run_system_healthcheck
from football.local_llm import call_ollama_json, local_llm_config
from football.models import Player, WorkspacePreference, WorkspaceSeason, WorkspaceTeam
from football.season_history_services import ensure_player_season_membership, ensure_workspace_player
from webstats import settings as app_settings


MODULE_SMOKE_MAP = {
    "task_builder": {
        "label": "Editor de tareas / pizarra",
        "kind": "script",
        "path": "scripts/e2e_tacticalpad_smoke.js",
    },
    "pdf_viewer": {
        "label": "Visor PDF",
        "kind": "script",
        "path": "scripts/e2e_pdf_viewer_smoke.js",
    },
    "video_studio": {
        "label": "Video Studio",
        "kind": "script",
        "path": "scripts/e2e_video_studio_smoke.js",
    },
    "library_source": {
        "label": "Biblioteca / fuentes",
        "kind": "script",
        "path": "scripts/e2e_library_source_smoke.js",
    },
    "popovers": {
        "label": "Popovers / overlays",
        "kind": "script",
        "path": "scripts/e2e_popovers_smoke.js",
    },
    "django_smoke": {
        "label": "Smoke Django rápido",
        "kind": "command",
        "command": "smoke",
    },
    "system_suite": {
        "label": "Smoke sistema ampliado",
        "kind": "command",
        "command": "smoke_system_suite",
    },
}

CORE_ROUTE_MAP = {
    "dashboard": {"label": "Home / dashboard", "name": "dashboard-home"},
    "match_hub": {"label": "Partido / match hub", "name": "match-hub"},
    "task_builder": {"label": "Editor de tareas", "name": "sessions-task-create"},
    "ai_trainer": {"label": "IA Trainer", "name": "ai-trainer"},
    "pdf_viewer": {"label": "Visor PDF", "name": "pdf-viewer"},
    "trainer_role": {"label": "Rol entrenador", "name": "coach-role-trainer"},
}

CORE_ASSET_MAP = {
    "task_builder_template": {
        "label": "Template task builder",
        "path": "football/templates/football/task_builder.html",
    },
    "dashboard_template": {
        "label": "Template dashboard",
        "path": "football/templates/football/dashboard.html",
    },
    "tactical_pad_js": {
        "label": "JS tactical pad",
        "path": "football/static/football/js/sessions_tactical_pad.js",
    },
    "video_studio_js": {
        "label": "JS video studio",
        "path": "football/static/football/js/analysis_video_studio.js",
    },
}

TOOL_SCHEMAS = {
    "check_status": {
        "label": "Revisar estado",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "status",
    },
    "inspect_recent_errors": {
        "label": "Inspeccionar errores recientes",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "recent_errors",
    },
    "check_critical_routes": {
        "label": "Revisar rutas críticas",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "critical_routes",
    },
    "inspect_runtime_config": {
        "label": "Inspeccionar config runtime",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "runtime_config",
    },
    "inspect_critical_paths": {
        "label": "Inspeccionar paths críticos",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "critical_paths",
    },
    "inspect_guard_history": {
        "label": "Inspeccionar histórico del guard",
        "kind": "inspect",
        "risk": "low",
        "confirmation_required": False,
        "runner": "guard_history",
    },
    "run_smoke": {
        "label": "Ejecutar smoke",
        "kind": "diagnostic",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "smoke",
    },
    "auto_fix": {
        "label": "Auto-fix seguro",
        "kind": "repair",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "autofix",
    },
    "regenerate_task_previews": {
        "label": "Regenerar previews",
        "kind": "maintenance",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "maintenance",
        "maintenance_action": "regenerate_task_previews",
    },
    "ai_trainer_reindex": {
        "label": "Reindexar IA Trainer",
        "kind": "maintenance",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "maintenance",
        "maintenance_action": "ai_trainer_reindex",
    },
    "inspect_repo_status": {
        "label": "Inspeccionar repositorio",
        "kind": "inspect",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "repo_status",
    },
    "run_operator_validation": {
        "label": "Validar operador",
        "kind": "diagnostic",
        "risk": "medium",
        "confirmation_required": False,
        "runner": "operator_validation",
    },
    "git_commit": {
        "label": "Crear commit",
        "kind": "publish",
        "risk": "high",
        "confirmation_required": True,
        "runner": "git_commit",
    },
    "git_push": {
        "label": "Hacer push",
        "kind": "publish",
        "risk": "high",
        "confirmation_required": True,
        "runner": "git_push",
    },
}

CHAT_ACTIONS = {
    "status": {
        "label": "Revisar estado",
        "tool": "check_status",
        "run_smoke": False,
        "auto_fix": False,
        "maintenance_action": "",
    },
    "smoke": {
        "label": "Ejecutar smoke",
        "tool": "run_smoke",
        "run_smoke": True,
        "auto_fix": False,
        "maintenance_action": "",
    },
    "auto_fix": {
        "label": "Auto-fix seguro",
        "tool": "auto_fix",
        "run_smoke": False,
        "auto_fix": True,
        "maintenance_action": "",
    },
    "previews": {
        "label": "Regenerar previews",
        "tool": "regenerate_task_previews",
        "run_smoke": False,
        "auto_fix": False,
        "maintenance_action": "regenerate_task_previews",
    },
    "reindex": {
        "label": "Reindexar IA Trainer",
        "tool": "ai_trainer_reindex",
        "run_smoke": False,
        "auto_fix": False,
        "maintenance_action": "ai_trainer_reindex",
    },
    "publish": {
        "label": "Commit y push",
        "tool": "git_push",
        "run_smoke": False,
        "auto_fix": False,
        "maintenance_action": "",
    },
}

AUTONOMY_MODES = {"advisor", "operator", "supervised"}
AUDIENCE_MODES = {"technical", "guided"}
MEMORY_PREF_KEY = "system_guard:memory:v3"
METRICS_PREF_KEY = "system_guard:metrics:v2"
SNAPSHOTS_PREF_KEY = "system_guard:snapshots:v1"
AUDIT_PREF_KEY = "system_guard:audit:v1"
TASK_QUEUE_PREF_KEY = "system_guard:task_queue:v1"
PROACTIVE_STATE_PREF_KEY = "system_guard:proactive_state:v1"
RUNBOOK_LIBRARY = {
    "user_navigation": {
        "label": "Navegación guiada",
        "goal": "Llevar al usuario al módulo correcto con el menor número de pasos.",
        "steps": [
            "Identificar destino funcional o pantalla objetivo.",
            "Confirmar ruta y contexto de equipo/workspace.",
            "Ejecutar navegación o dejar acceso directo.",
        ],
    },
    "user_guidance": {
        "label": "Guía de usuario",
        "goal": "Explicar la pantalla y el siguiente paso útil sin ruido técnico.",
        "steps": [
            "Leer el contexto de pantalla actual.",
            "Resumir qué se puede hacer aquí.",
            "Proponer 1-2 siguientes acciones concretas.",
        ],
    },
    "user_execution": {
        "label": "Ejecución asistida",
        "goal": "Resolver una petición funcional del usuario sin sacarlo del flujo.",
        "steps": [
            "Entender la acción solicitada y los datos disponibles.",
            "Pedir solo los campos imprescindibles si faltan.",
            "Ejecutar la acción y devolver resultado trazable.",
        ],
    },
    "silent_diagnostics": {
        "label": "Diagnóstico silencioso",
        "goal": "Inspeccionar estado, errores y configuración sin interrumpir al usuario.",
        "steps": [
            "Diagnosticar estado base.",
            "Revisar evidencia prioritaria.",
            "Resumir hallazgos y riesgo operativo.",
        ],
    },
    "safe_repair": {
        "label": "Reparación segura",
        "goal": "Corregir incidencias controladas y verificar que el sistema sigue estable.",
        "steps": [
            "Diagnosticar la incidencia.",
            "Aplicar corrección segura o remediación propuesta.",
            "Verificar con check/smoke.",
        ],
    },
    "operator_publish": {
        "label": "Publicación gobernada",
        "goal": "Validar, consolidar cambios y publicar solo con confirmación.",
        "steps": [
            "Inspeccionar repo y validación.",
            "Crear commit limpio.",
            "Solicitar confirmación y publicar.",
        ],
    },
    "maintenance_runbook": {
        "label": "Mantenimiento operativo",
        "goal": "Ejecutar acciones internas del sistema con trazabilidad.",
        "steps": [
            "Identificar acción de mantenimiento.",
            "Ejecutar herramienta asociada.",
            "Validar resultado y registrar salida.",
        ],
    },
}
PROACTIVE_DETECTORS = {
    "ollama_unreachable": {
        "severity": "warning",
        "runbook": "silent_diagnostics",
        "task_kind": "diagnose",
        "summary": "Ollama local no responde y conviene abrir diagnóstico automático.",
        "tools": ["check_status", "inspect_recent_errors", "inspect_runtime_config"],
        "auto_execute": True,
    },
    "path_missing_static_root": {
        "severity": "warning",
        "runbook": "silent_diagnostics",
        "task_kind": "diagnose",
        "summary": "Falta un path crítico y conviene revisar paths/runtime.",
        "tools": ["check_status", "inspect_critical_paths", "inspect_runtime_config"],
        "auto_execute": True,
    },
    "runtime_blockers": {
        "severity": "critical",
        "runbook": "silent_diagnostics",
        "task_kind": "diagnose",
        "summary": "Se han detectado blockers activos en el sistema.",
        "tools": ["check_status", "inspect_recent_errors", "check_critical_routes"],
        "auto_execute": True,
    },
    "route_failure": {
        "severity": "critical",
        "runbook": "silent_diagnostics",
        "task_kind": "diagnose",
        "summary": "Hay rutas críticas fallando y hay que revisar el sistema.",
        "tools": ["check_status", "check_critical_routes", "inspect_recent_errors"],
        "auto_execute": True,
    },
    "repeated_regression": {
        "severity": "warning",
        "runbook": "silent_diagnostics",
        "task_kind": "diagnose",
        "summary": "Hay regresiones repetidas que conviene analizar de forma continua.",
        "tools": ["check_status", "inspect_guard_history", "inspect_recent_errors"],
        "auto_execute": True,
    },
}
KNOWN_FIXES = {
    "DisallowedHost": {
        "title": "Corregir `DisallowedHost`",
        "files": ["webstats/settings.py", "render.yaml"],
        "proposal": "Revisar `ALLOWED_HOSTS`, `APP_PUBLIC_BASE_URL`, `LANDING_HOSTS` y `CSRF_TRUSTED_ORIGINS` para incluir el host público real sin abrir wildcard en producción.",
    },
    "HTTPS_on_HTTP_devserver": {
        "title": "Evitar HTTPS sobre `runserver`",
        "files": ["scripts/*", "README.md"],
        "proposal": "Asegurar que el entorno local abre `http://` y documentar que `runserver` no termina TLS.",
    },
    "missing_route": {
        "title": "Reparar rutas críticas",
        "files": ["football/urls.py", "football/views.py"],
        "proposal": "Revisar `reverse`, nombres de ruta e imports de vistas críticas.",
    },
    "path_missing_static_root": {
        "title": "Restaurar `static_root`",
        "files": ["render.yaml", "webstats/settings.py"],
        "proposal": "Asegurar que `STATIC_ROOT` existe en el entorno y que el despliegue crea o monta la ruta correctamente.",
    },
    "ollama_unreachable": {
        "title": "Recuperar Ollama local",
        "files": ["scripts/start_with_ollama.sh", "render.yaml"],
        "proposal": "Revisar arranque del servicio, puerto `11434`, modelo configurado y modo degradado cuando el LLM no esté disponible.",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default or 0)


def _truncate(value, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= int(limit or 0):
        return text
    return text[: max(0, int(limit or 0) - 1)].rstrip() + "…"


def _path_status(path_str: str) -> dict:
    path = Path(settings.BASE_DIR) / path_str
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def _module_inventory() -> dict:
    out = {}
    for key, meta in MODULE_SMOKE_MAP.items():
        if meta.get("kind") == "script":
            out[key] = {
                "label": meta.get("label"),
                "kind": "script",
                **_path_status(str(meta.get("path") or "")),
            }
        else:
            out[key] = {
                "label": meta.get("label"),
                "kind": "command",
                "command": str(meta.get("command") or ""),
                "available": True,
            }
    return out


def _route_inventory() -> dict:
    out = {}
    for key, meta in CORE_ROUTE_MAP.items():
        name = str(meta.get("name") or "").strip()
        try:
            out[key] = {
                "label": meta.get("label"),
                "name": name,
                "ok": True,
                "url": reverse(name),
            }
        except NoReverseMatch as exc:
            out[key] = {
                "label": meta.get("label"),
                "name": name,
                "ok": False,
                "url": "",
                "error": f"NoReverseMatch: {exc}",
            }
    return out


def _asset_inventory() -> dict:
    out = {}
    for key, meta in CORE_ASSET_MAP.items():
        path = Path(settings.BASE_DIR) / str(meta.get("path") or "")
        out[key] = {
            "label": meta.get("label"),
            "path": str(path),
            "ok": path.exists(),
            "size": int(path.stat().st_size) if path.exists() else 0,
        }
    return out


def _tool_catalog() -> list[dict]:
    rows = []
    for key, schema in TOOL_SCHEMAS.items():
        rows.append(
            {
                "key": key,
                "label": schema.get("label"),
                "kind": schema.get("kind"),
                "risk": schema.get("risk"),
                "confirmation_required": bool(schema.get("confirmation_required")),
                "maintenance_action": str(schema.get("maintenance_action") or ""),
            }
        )
    return rows


def _compact_query(params: dict) -> str:
    safe = {str(key): value for key, value in (params or {}).items() if value not in (None, "", 0, "0")}
    return f"?{urlencode(safe)}" if safe else ""


def _guard_route_catalog(page_context=None) -> list[dict]:
    context = page_context if isinstance(page_context, dict) else {}
    team_id = _safe_int(context.get("team_id"), 0)
    workspace_id = _safe_int(context.get("workspace_id"), 0)
    team_qs = {"team": team_id} if team_id else {}
    workspace_qs = {"workspace": workspace_id} if workspace_id else {}
    rows = []
    definitions = [
        {
            "key": "dashboard",
            "label": "Portada",
            "url_name": "dashboard-home",
            "keywords": ["portada", "inicio", "home", "dashboard"],
            "query": team_qs,
        },
        {
            "key": "analysis",
            "label": "Vídeo análisis",
            "url_name": "analysis",
            "keywords": ["video analisis", "vídeo análisis", "analisis", "análisis", "video", "vídeo"],
            "query": team_qs,
        },
        {
            "key": "library",
            "label": "Biblioteca de tareas",
            "url_name": "sessions",
            "keywords": ["biblioteca de tareas", "biblioteca", "tareas", "ejercicios", "task library"],
            "query": {"tab": "library", "library_repo": "traditional", **team_qs, **workspace_qs},
        },
        {
            "key": "task_builder",
            "label": "Crear tarea",
            "url_name": "sessions-task-create",
            "keywords": ["crear tarea", "nueva tarea", "pizarra", "editor"],
            "query": {**team_qs, **workspace_qs},
        },
        {
            "key": "sessions",
            "label": "Entrenamiento",
            "url_name": "sessions",
            "keywords": ["entrenamiento", "sesiones", "microciclo", "entrenos"],
            "query": team_qs,
        },
        {
            "key": "match",
            "label": "Partido",
            "url_name": "match-hub",
            "keywords": ["partido", "match", "convocatoria", "once inicial"],
            "query": team_qs,
        },
        {
            "key": "players",
            "label": "Jugadores",
            "url_name": "coach-roster",
            "keywords": ["jugadores", "jugador", "plantilla", "roster"],
            "query": {"tab": "stats", **team_qs},
        },
        {
            "key": "agenda",
            "label": "Agenda",
            "url_name": "team-agenda",
            "keywords": ["agenda", "calendario"],
            "query": team_qs,
        },
        {
            "key": "staff",
            "label": "Staff",
            "url_name": "staff-directory",
            "keywords": ["staff", "cuerpo tecnico", "cuerpo técnico"],
            "query": team_qs,
        },
        {
            "key": "tactics",
            "label": "Táctica",
            "url_name": "coach-tactics",
            "keywords": ["tactica", "táctica", "abp", "playbook"],
            "query": team_qs,
        },
        {
            "key": "reports",
            "label": "Informes",
            "url_name": "reports-hub",
            "keywords": ["informes", "reporte", "reportes", "pdf"],
            "query": team_qs,
        },
        {
            "key": "ai_trainer",
            "label": "IA Trainer",
            "url_name": "ai-trainer",
            "keywords": ["ia trainer", "ai trainer", "trainer"],
            "query": {**team_qs, **workspace_qs},
        },
    ]
    for row in definitions:
        try:
            base_url = reverse(str(row.get("url_name") or "").strip())
        except NoReverseMatch:
            continue
        rows.append({
            "key": str(row.get("key") or ""),
            "label": str(row.get("label") or ""),
            "url": f"{base_url}{_compact_query(row.get('query') or {})}",
            "keywords": [str(item or "") for item in (row.get("keywords") or []) if str(item or "").strip()],
        })
    return rows


def _match_route_target(question: str, page_context=None) -> dict | None:
    text = str(question or "").strip().lower()
    if not text:
        return None
    route_rows = _guard_route_catalog(page_context)
    best = None
    for route in route_rows:
        score = 0
        for keyword in route.get("keywords") or []:
            token = str(keyword or "").strip().lower()
            if token and token in text:
                score += max(2, len(token.split()) * 2)
        if score > 0 and (best is None or score > best.get("score", 0)):
            best = {"score": score, **route}
    return best if best and best.get("score", 0) > 0 else None


def _build_task_profile(question: str, *, intent: str, maintenance_action: str = "", page_context=None) -> dict:
    route_target = _match_route_target(question, page_context)
    kind = "support"
    scope = "user"
    silent_mode = True
    runbook_key = "silent_diagnostics"
    if route_target and re.search(r"\b(abre|abrir|ll[ée]vame|llevame|ve a|ir a|quiero ir|quiero abrir|quiero ver)\b", str(question or "").lower()):
        kind = "navigate"
        scope = "user"
        silent_mode = False
        runbook_key = "user_navigation"
    elif intent in {"create_player"}:
        kind = "execute"
        scope = "user"
        silent_mode = False
        runbook_key = "user_execution"
    elif intent == "guide_user":
        kind = "guide"
        scope = "user"
        silent_mode = False
        runbook_key = "user_guidance"
    elif intent in {"publish_commit_push", "publish_commit", "publish_push"} or maintenance_action in {"git_commit_push", "git_commit", "git_push"}:
        kind = "publish"
        scope = "code"
        silent_mode = True
        runbook_key = "operator_publish"
    elif intent in {"repair"} or maintenance_action in {"regenerate_task_previews", "ai_trainer_reindex"}:
        kind = "repair" if intent == "repair" else "maintenance"
        scope = "system" if kind == "repair" else "maintenance"
        silent_mode = True
        runbook_key = "safe_repair" if kind == "repair" else "maintenance_runbook"
    elif intent in {"inspect_repo", "operator_validate", "inspect_errors", "inspect_routes", "inspect_config", "inspect_paths", "inspect_history", "diagnose_smoke", "diagnose_status"}:
        kind = "diagnose"
        scope = "system"
        silent_mode = True
        runbook_key = "silent_diagnostics"
    return {
        "kind": kind,
        "scope": scope,
        "silent_mode": bool(silent_mode),
        "route_target": route_target or {},
        "runbook_key": runbook_key,
        "current_page": str((page_context or {}).get("page") or "").strip()[:120] if isinstance(page_context, dict) else "",
    }


def _runbook_payload(runbook_key: str, *, task: dict, requested_tools: list[str], confirm_required: bool) -> dict:
    meta = RUNBOOK_LIBRARY.get(runbook_key) or RUNBOOK_LIBRARY["silent_diagnostics"]
    stages = []
    for step in meta.get("steps") or []:
        stages.append({"label": str(step), "done": False})
    if requested_tools:
        stages.append({"label": f"Herramientas: {', '.join(requested_tools[:4])}", "done": False})
    if confirm_required:
        stages.append({"label": "Esperar confirmación antes de cambios sensibles", "done": False})
    return {
        "key": str(runbook_key or ""),
        "label": str(meta.get("label") or ""),
        "goal": str(meta.get("goal") or ""),
        "stages": stages[:6],
        "task_kind": str((task or {}).get("kind") or ""),
    }


def _followup_actions(task: dict, planner: dict, *, page_context=None) -> list[dict]:
    actions = []
    route_target = task.get("route_target") if isinstance(task, dict) else {}
    if isinstance(route_target, dict) and route_target.get("url"):
        actions.append({
            "type": "navigate",
            "label": f"Abrir {route_target.get('label')}",
            "url": str(route_target.get("url") or ""),
            "reason": "Navegación directa a la zona solicitada.",
        })
    if task.get("kind") == "guide":
        for route in _guard_route_catalog(page_context)[:3]:
            actions.append({
                "type": "navigate",
                "label": f"Ir a {route.get('label')}",
            "url": str(route.get("url") or ""),
            "reason": "Acceso rápido sugerido por Ollana.",
        })
    if task.get("kind") == "execute":
        player_route = next((row for row in _guard_route_catalog(page_context) if row.get("key") == "players"), None)
        if player_route and player_route.get("url"):
            actions.append({
                "type": "navigate",
                "label": "Abrir plantilla",
                "url": str(player_route.get("url") or ""),
                "reason": "Acceso directo a la gestión de jugadores.",
            })
    if planner.get("confirm_required"):
        actions.append({
            "type": "confirm_execution",
            "label": "Confirmar ejecución",
            "reason": str(planner.get("confirmation_text") or "Acción sensible pendiente."),
        })
    if task.get("kind") in {"support", "diagnose", "repair"}:
        actions.append({
            "type": "prompt",
            "label": "Explicar incidencia",
            "prompt": "Explícame la causa raíz y el siguiente paso recomendado.",
            "reason": "Pedir una guía más concreta al guard.",
        })
    return actions[:4]


def _environment_snapshot() -> dict:
    return {
        "generated_at": _now_iso(),
        "hostname": socket.gethostname(),
        "debug": bool(getattr(settings, "DEBUG", False)),
        "base_dir": str(settings.BASE_DIR),
        "database_engine": str(settings.DATABASES.get("default", {}).get("ENGINE") or ""),
        "media_root": str(getattr(settings, "MEDIA_ROOT", "") or ""),
        "static_root": str(getattr(settings, "STATIC_ROOT", "") or ""),
        "use_s3_media": bool(getattr(settings, "USE_S3_MEDIA", False)),
        "install_ollama": str(os.getenv("INSTALL_OLLAMA") or "").strip(),
        "ai_trainer_local_llm_enabled": str(os.getenv("AI_TRAINER_LOCAL_LLM_ENABLED") or "").strip(),
        "ai_trainer_local_llm_provider": str(os.getenv("AI_TRAINER_LOCAL_LLM_PROVIDER") or "").strip(),
        "ai_trainer_local_llm_model": str(os.getenv("AI_TRAINER_LOCAL_LLM_MODEL") or "").strip(),
    }


def _django_error_log_path() -> Path:
    return Path(settings.BASE_DIR) / "django_error.log"


def _inspect_recent_errors(*, max_lines: int = 80) -> dict:
    path = _django_error_log_path()
    if not path.exists():
        return {
            "ok": False,
            "action": "inspect_recent_errors",
            "error": "log_missing",
            "path": str(path),
            "patterns": [],
            "recent_lines": [],
        }
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as exc:
        return {
            "ok": False,
            "action": "inspect_recent_errors",
            "error": f"{exc.__class__.__name__}: {exc}",
            "path": str(path),
            "patterns": [],
            "recent_lines": [],
        }
    tail = [str(line or "").rstrip() for line in lines[-max_lines:] if str(line or "").strip()]
    buckets = {
        "DisallowedHost": 0,
        "HTTPS_on_HTTP_devserver": 0,
        "Traceback": 0,
        "ERROR_lines": 0,
    }
    for line in tail:
        if "DisallowedHost" in line or "Invalid HTTP_HOST" in line:
            buckets["DisallowedHost"] += 1
        if "development server over HTTPS" in line:
            buckets["HTTPS_on_HTTP_devserver"] += 1
        if line.startswith("Traceback"):
            buckets["Traceback"] += 1
        if line.startswith("ERROR "):
            buckets["ERROR_lines"] += 1
    patterns = [{"name": key, "count": count} for key, count in buckets.items() if count > 0]
    return {
        "ok": True,
        "action": "inspect_recent_errors",
        "path": str(path),
        "patterns": patterns,
        "recent_lines": tail[-12:],
        "line_count": len(tail),
    }


def _check_critical_routes() -> dict:
    routes = _route_inventory()
    failing = []
    ok_count = 0
    for key, row in routes.items():
        if isinstance(row, dict) and row.get("ok"):
            ok_count += 1
        elif isinstance(row, dict):
            failing.append({
                "key": key,
                "name": str(row.get("name") or ""),
                "error": str(row.get("error") or ""),
            })
    return {
        "ok": not failing,
        "action": "check_critical_routes",
        "ok_count": ok_count,
        "failing": failing[:8],
    }


def _inspect_runtime_config() -> dict:
    allowed_hosts = [str(x) for x in list(getattr(app_settings, "ALLOWED_HOSTS", []) or []) if str(x or "").strip()]
    csrf_origins = [str(x) for x in list(getattr(app_settings, "CSRF_TRUSTED_ORIGINS", []) or []) if str(x or "").strip()]
    app_public = str(os.getenv("APP_PUBLIC_BASE_URL") or "").strip()
    render_host = str(os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    landing_hosts = str(os.getenv("LANDING_HOSTS") or "").strip()
    warnings = []
    if "testserver" not in allowed_hosts:
        warnings.append("testserver_no_esta_en_allowed_hosts")
    if any("0.0.0.0" in host for host in allowed_hosts):
        warnings.append("allowed_hosts_contiene_0_0_0_0")
    if app_public and not any(app_public.split("://")[-1].split("/")[0].split(":")[0] in host for host in allowed_hosts):
        warnings.append("app_public_base_url_no_reflejado_en_allowed_hosts")
    return {
        "ok": True,
        "action": "inspect_runtime_config",
        "debug": bool(getattr(app_settings, "DEBUG", False)),
        "allowed_hosts": allowed_hosts[:40],
        "csrf_trusted_origins": csrf_origins[:60],
        "app_public_base_url": app_public,
        "render_external_hostname": render_host,
        "landing_hosts_env": landing_hosts,
        "warnings": warnings,
    }


def _inspect_critical_paths() -> dict:
    candidates = {
        "base_dir": Path(settings.BASE_DIR),
        "static_root": Path(str(getattr(settings, "STATIC_ROOT", "") or "")).expanduser(),
        "media_root": Path(str(getattr(settings, "MEDIA_ROOT", "") or "")).expanduser(),
        "data_input": Path(settings.BASE_DIR) / "data" / "input",
        "data_debug": Path(settings.BASE_DIR) / "data" / "debug",
    }
    rows = []
    for key, path in candidates.items():
        exists = bool(str(path)) and path.exists()
        rows.append(
            {
                "key": key,
                "path": str(path),
                "exists": exists,
                "is_dir": path.is_dir() if exists else False,
            }
        )
    return {
        "ok": all(bool(row.get("exists")) for row in rows if row.get("key") != "static_root"),
        "action": "inspect_critical_paths",
        "paths": rows,
    }


def _probe_ollama(cfg: dict) -> dict:
    started_at = time.monotonic()
    enabled = bool(cfg.get("enabled"))
    base_url = str(cfg.get("base_url") or "").rstrip("/")
    model = str(cfg.get("model") or "").strip()
    if not enabled:
        return {
            "enabled": False,
            "ok": False,
            "reachable": False,
            "model_present": False,
            "base_url": base_url,
            "model": model,
            "error": "disabled",
            "latency_ms": 0,
        }
    if str(cfg.get("provider") or "").lower() != "ollama":
        return {
            "enabled": True,
            "ok": False,
            "reachable": False,
            "model_present": False,
            "base_url": base_url,
            "model": model,
            "error": "unsupported_provider",
            "latency_ms": 0,
        }
    req = urllib.request.Request(f"{base_url}/api/tags", headers={"Content-Type": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(2, _safe_int(cfg.get("timeout"), 8))) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return {
            "enabled": True,
            "ok": False,
            "reachable": False,
            "model_present": False,
            "base_url": base_url,
            "model": model,
            "error": f"ollama_http_{exc.code}",
            "latency_ms": int((time.monotonic() - started_at) * 1000),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "ok": False,
            "reachable": False,
            "model_present": False,
            "base_url": base_url,
            "model": model,
            "error": f"ollama_unreachable:{exc}",
            "latency_ms": int((time.monotonic() - started_at) * 1000),
        }
    models = payload.get("models") if isinstance(payload, dict) else []
    names = []
    for item in models if isinstance(models, list) else []:
        if isinstance(item, dict):
            names.append(str(item.get("model") or item.get("name") or "").strip())
    model_present = model in names
    return {
        "enabled": True,
        "ok": bool(model_present),
        "reachable": True,
        "model_present": bool(model_present),
        "base_url": base_url,
        "model": model,
        "models": names[:30],
        "error": "" if model_present else "model_missing",
        "latency_ms": int((time.monotonic() - started_at) * 1000),
    }


def _availability_snapshot(cfg: dict, probe: dict) -> dict:
    state = "down"
    if not cfg.get("enabled"):
        state = "disabled"
    elif probe.get("reachable") and probe.get("model_present"):
        state = "up"
    elif probe.get("reachable"):
        state = "degraded"
    return {
        "provider": str(cfg.get("provider") or ""),
        "model": str(cfg.get("model") or ""),
        "base_url": str(cfg.get("base_url") or ""),
        "timeout": _safe_int(cfg.get("timeout"), 0),
        "state": state,
        "enabled": bool(cfg.get("enabled")),
        "reachable": bool(probe.get("reachable")),
        "model_present": bool(probe.get("model_present")),
        "latency_ms": _safe_int(probe.get("latency_ms"), 0),
        "error": str(probe.get("error") or ""),
        "checked_at": _now_iso(),
    }


def _pref_value(workspace, key: str, default):
    if not workspace:
        return default
    try:
        pref = WorkspacePreference.objects.filter(workspace=workspace, key=key).only("value").first()
    except Exception:
        return default
    if not pref:
        return default
    return pref.value if isinstance(pref.value, type(default)) else default


def _store_pref_value(workspace, key: str, value):
    if not workspace:
        return
    try:
        WorkspacePreference.objects.update_or_create(
            workspace=workspace,
            key=key,
            defaults={"value": value},
        )
    except Exception:
        return


def _snapshot_payload(report: dict, response: dict, executions: list[dict]) -> dict:
    issue_summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    issue_ids = [str(row.get("id") or "") for row in issues[:20] if isinstance(row, dict)]
    availability = ((((report.get("evidence") or {}).get("local_llm") or {}).get("availability")) or {})
    return {
        "created_at": _now_iso(),
        "status": str(response.get("status") or "").strip()[:32],
        "blockers": _safe_int(issue_summary.get("blockers"), 0),
        "warnings": _safe_int(issue_summary.get("warnings"), 0),
        "issue_ids": issue_ids,
        "llm_state": str(availability.get("state") or "").strip()[:32],
        "executed_tools": [str(row.get("tool") or "") for row in executions if isinstance(row, dict)][:8],
    }


def _load_snapshots(workspace) -> list[dict]:
    payload = _pref_value(workspace, SNAPSHOTS_PREF_KEY, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)][:20]


def _store_snapshot(workspace, *, report: dict, response: dict, executions: list[dict]):
    if not workspace:
        return
    rows = _load_snapshots(workspace)
    rows.insert(0, _snapshot_payload(report, response, executions))
    _store_pref_value(workspace, SNAPSHOTS_PREF_KEY, rows[:20])


def _compare_snapshots(current: dict, previous: dict | None) -> dict:
    if not isinstance(previous, dict):
        return {
            "has_baseline": False,
            "regressions": [],
            "improvements": [],
            "repeated_issues": [],
        }
    regressions = []
    improvements = []
    repeated = sorted(set(current.get("issue_ids") or []).intersection(set(previous.get("issue_ids") or [])))
    current_blockers = _safe_int(current.get("blockers"), 0)
    prev_blockers = _safe_int(previous.get("blockers"), 0)
    current_warnings = _safe_int(current.get("warnings"), 0)
    prev_warnings = _safe_int(previous.get("warnings"), 0)
    if current_blockers > prev_blockers:
        regressions.append(f"Blockers suben de {prev_blockers} a {current_blockers}")
    elif current_blockers < prev_blockers:
        improvements.append(f"Blockers bajan de {prev_blockers} a {current_blockers}")
    if current_warnings > prev_warnings:
        regressions.append(f"Warnings suben de {prev_warnings} a {current_warnings}")
    elif current_warnings < prev_warnings:
        improvements.append(f"Warnings bajan de {prev_warnings} a {current_warnings}")
    if current.get("llm_state") != previous.get("llm_state"):
        if current.get("llm_state") in {"down", "degraded"}:
            regressions.append(f"LLM pasa de {previous.get('llm_state')} a {current.get('llm_state')}")
        else:
            improvements.append(f"LLM pasa de {previous.get('llm_state')} a {current.get('llm_state')}")
    return {
        "has_baseline": True,
        "regressions": regressions[:6],
        "improvements": improvements[:6],
        "repeated_issues": repeated[:8],
    }


def _inspect_guard_history(workspace) -> dict:
    rows = _load_snapshots(workspace)
    if not rows:
        return {
            "ok": True,
            "action": "inspect_guard_history",
            "history_count": 0,
            "trend": "sin_historial",
            "recent_statuses": [],
            "top_repeated_issues": [],
        }
    recent_statuses = [str(row.get("status") or "") for row in rows[:6] if str(row.get("status") or "").strip()]
    issue_counter = {}
    for row in rows[:10]:
        for issue_id in (row.get("issue_ids") or [])[:12]:
            issue_counter[issue_id] = issue_counter.get(issue_id, 0) + 1
    top_repeated = sorted(issue_counter.items(), key=lambda item: (-item[1], item[0]))[:6]
    blockers_now = _safe_int(rows[0].get("blockers"), 0)
    blockers_prev = _safe_int(rows[1].get("blockers"), blockers_now) if len(rows) > 1 else blockers_now
    trend = "estable"
    if blockers_now > blockers_prev:
        trend = "empeora"
    elif blockers_now < blockers_prev:
        trend = "mejora"
    return {
        "ok": True,
        "action": "inspect_guard_history",
        "history_count": len(rows),
        "trend": trend,
        "recent_statuses": recent_statuses,
        "top_repeated_issues": [{"issue_id": key, "count": count} for key, count in top_repeated],
    }


def _observability_summary(workspace) -> dict:
    rows = _load_snapshots(workspace)
    metrics = _pref_value(workspace, METRICS_PREF_KEY, {})
    if not isinstance(metrics, dict):
        metrics = {}
    memory = _load_memory(workspace) if workspace else {}
    audit_rows = _load_audit_log(workspace) if workspace else []
    history = _inspect_guard_history(workspace)
    llm_counter = {}
    for row in rows[:10]:
        state = str(row.get("llm_state") or "").strip() or "unknown"
        llm_counter[state] = llm_counter.get(state, 0) + 1
    llm_states = [
        {"state": state, "count": count}
        for state, count in sorted(llm_counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    degraded_turns = _safe_int(metrics.get("degraded_turns"), 0)
    turns = _safe_int(metrics.get("turns"), len(rows))
    degraded_rate = int(round((degraded_turns / turns) * 100)) if turns > 0 else 0
    top_state = llm_states[0]["state"] if llm_states else "unknown"
    latest_diff = _compare_snapshots(rows[0], rows[1] if len(rows) > 1 else None) if rows else {
        "has_baseline": False,
        "regressions": [],
        "improvements": [],
        "repeated_issues": [],
    }
    if top_state == "up" and degraded_rate <= 10:
        llm_stability = "estable"
    elif top_state in {"degraded", "down"} or degraded_rate >= 40:
        llm_stability = "degradada"
    else:
        llm_stability = "variable"
    regressions = latest_diff.get("regressions") if isinstance(latest_diff.get("regressions"), list) else []
    improvements = latest_diff.get("improvements") if isinstance(latest_diff.get("improvements"), list) else []
    blockers_now = _safe_int(rows[0].get("blockers"), 0) if rows else 0
    if regressions or blockers_now > 0 or llm_stability == "degradada":
        health_state = "red"
    elif improvements or history.get("trend") == "mejora" or llm_stability == "estable":
        health_state = "green"
    else:
        health_state = "amber"
    alerts = []
    for item in regressions[:2]:
        alerts.append({"level": "regression", "text": str(item)})
    for item in improvements[:1]:
        alerts.append({"level": "improvement", "text": str(item)})
    repeated_items = history.get("top_repeated_issues") if isinstance(history.get("top_repeated_issues"), list) else []
    if repeated_items:
        alerts.append({
            "level": "repeat",
            "text": f"Incidencia repetida: {repeated_items[0].get('issue_id')} x{repeated_items[0].get('count')}",
        })
    return {
        "available": bool(rows or turns or memory),
        "history_count": len(rows),
        "trend": history.get("trend") or "sin_historial",
        "recent_statuses": history.get("recent_statuses") or [],
        "repeated_issues": history.get("top_repeated_issues") or [],
        "health_state": health_state,
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
        "alerts": alerts[:4],
        "turns": turns,
        "degraded_turns": degraded_turns,
        "degraded_rate_pct": degraded_rate,
        "confirmations": _safe_int(metrics.get("confirmations"), 0),
        "executed_tools": _safe_int(metrics.get("executed_tools"), 0),
        "last_latency_ms": _safe_int(metrics.get("last_latency_ms"), 0),
        "last_status": str(metrics.get("last_status") or memory.get("last_status") or "").strip()[:32],
        "last_updated": str(metrics.get("last_updated") or memory.get("last_updated") or "").strip()[:64],
        "llm_stability": llm_stability,
        "llm_states": llm_states[:4],
        "summary": str(memory.get("summary") or "").strip()[:280],
        "recent_actions": [str(item) for item in (memory.get("recent_actions") or [])[:4]],
        "recent_successes": [str(item) for item in (memory.get("recent_successes") or [])[:4]],
        "audit_count": len(audit_rows),
        "recent_audits": audit_rows[:3],
        "task_queue": _task_state_counts(_load_task_queue(workspace)) if workspace else {"pending": 0, "running": 0, "completed": 0, "blocked": 0},
        "task_queue_preview": _load_task_queue(workspace)[:3] if workspace else [],
        "proactive_state": _load_proactive_state(workspace) if workspace else {},
    }


def _load_audit_log(workspace) -> list[dict]:
    payload = _pref_value(workspace, AUDIT_PREF_KEY, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)][:60]


def _append_audit_log(workspace, event: dict):
    if not workspace or not isinstance(event, dict):
        return
    rows = _load_audit_log(workspace)
    rows.insert(0, event)
    _store_pref_value(workspace, AUDIT_PREF_KEY, rows[:60])


def _detect_proactive_incidents(report: dict, *, workspace=None) -> list[dict]:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    issue_ids = {str(row.get("id") or "").strip() for row in issues if isinstance(row, dict)}
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    detections = []
    for issue_id in sorted(issue_ids):
        meta = PROACTIVE_DETECTORS.get(issue_id)
        if not meta:
            continue
        detections.append({
            "detector": issue_id,
            "severity": str(meta.get("severity") or "warning"),
            "runbook": str(meta.get("runbook") or "silent_diagnostics"),
            "task_kind": str(meta.get("task_kind") or "diagnose"),
            "title": str(meta.get("summary") or issue_id).strip(),
            "summary": str(meta.get("summary") or issue_id).strip(),
            "tools": [str(x) for x in (meta.get("tools") or []) if str(x or "").strip()],
            "auto_execute": bool(meta.get("auto_execute")),
        })
    if _safe_int(summary.get("blockers"), 0) > 0 and not any(row.get("detector") == "runtime_blockers" for row in detections):
        meta = PROACTIVE_DETECTORS["runtime_blockers"]
        detections.append({
            "detector": "runtime_blockers",
            "severity": meta["severity"],
            "runbook": meta["runbook"],
            "task_kind": meta["task_kind"],
            "title": f"Blockers activos: {_safe_int(summary.get('blockers'), 0)}",
            "summary": meta["summary"],
            "tools": meta["tools"],
            "auto_execute": bool(meta["auto_execute"]),
        })
    history = _inspect_guard_history(workspace) if workspace else {}
    repeated = history.get("top_repeated_issues") if isinstance(history.get("top_repeated_issues"), list) else []
    if repeated:
        meta = PROACTIVE_DETECTORS["repeated_regression"]
        detections.append({
            "detector": "repeated_regression",
            "severity": meta["severity"],
            "runbook": meta["runbook"],
            "task_kind": meta["task_kind"],
            "title": f"Incidencia repetida: {repeated[0].get('issue_id')}",
            "summary": meta["summary"],
            "tools": meta["tools"],
            "auto_execute": bool(meta["auto_execute"]),
        })
    return detections[:8]


def _task_result_summary(executions: list[dict]) -> str:
    if not executions:
        return ""
    ok_count = sum(1 for row in executions if isinstance(row, dict) and row.get("ok"))
    total = len([row for row in executions if isinstance(row, dict)])
    first_error = next((str(row.get("detail") or row.get("tool") or "") for row in executions if isinstance(row, dict) and not row.get("ok")), "")
    if first_error:
        return _truncate(f"{ok_count}/{total} herramientas correctas. Error: {first_error}", 220)
    return _truncate(f"{ok_count}/{total} herramientas completadas correctamente.", 220)


def _execute_queued_task(workspace, task: dict) -> dict:
    if not workspace or not isinstance(task, dict):
        return task or {}
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return task
    _update_task_entry(workspace, task_id, status="running")
    executions = _execute_tools(task.get("tools") or [], workspace=workspace, question=str(task.get("question") or task.get("title") or ""))
    ok = all(bool(row.get("ok")) for row in executions if isinstance(row, dict)) if executions else False
    updated = _update_task_entry(
        workspace,
        task_id,
        status="completed" if ok else "blocked",
        executions=executions,
        result_summary=_task_result_summary(executions),
        finished_at=_now_iso(),
    )
    return updated or task


def run_proactive_guard_cycle(*, workspace, actor_id=None, allow_safe_repairs: bool = True, page_context=None) -> dict:
    if not workspace:
        return {"ok": False, "error": "workspace_required", "queue": []}
    report = run_system_guard(
        run_smoke=False,
        smoke_verbosity=1,
        run_llm=False,
        auto_fix=False,
        page_context=page_context or {"page": "guard-proactive"},
        memory=_merge_memory(_load_memory(workspace), _load_memory_for_actor(workspace, actor_id=actor_id)),
    )
    detections = _detect_proactive_incidents(report, workspace=workspace)
    created = []
    executed = []
    for detection in detections:
        task = _new_task_entry(
            detector=str(detection.get("detector") or ""),
            title=str(detection.get("title") or detection.get("summary") or ""),
            summary=str(detection.get("summary") or ""),
            severity=str(detection.get("severity") or "warning"),
            runbook=str(detection.get("runbook") or "silent_diagnostics"),
            task_kind=str(detection.get("task_kind") or "diagnose"),
            tools=list(detection.get("tools") or []),
            source="proactive",
            question=f"Runbook proactivo: {str(detection.get('title') or detection.get('summary') or '')}",
            auto_execute=bool(detection.get("auto_execute")),
        )
        saved = _enqueue_task(workspace, task)
        created.append(saved)
        if allow_safe_repairs and bool(saved.get("auto_execute")) and str(saved.get("status") or "") == "pending":
            executed.append(_execute_queued_task(workspace, saved))
    state_payload = {
        "last_cycle_at": _now_iso(),
        "last_detection_count": len(detections),
        "last_created_count": len(created),
        "last_executed_count": len(executed),
    }
    _store_proactive_state(workspace, state_payload)
    _append_audit_log(workspace, {
        "created_at": _now_iso(),
        "actor_id": int(actor_id or 0),
        "question": "Ciclo proactivo del guard",
        "status": "ok" if report.get("ok") else "watch",
        "task_kind": "proactive_cycle",
        "runbook": "silent_diagnostics",
        "confirmed": False,
        "executed_tools": [str(row.get("tool") or "") for row in executed if isinstance(row, dict)],
        "silent_mode": True,
    })
    queue_rows = _load_task_queue(workspace)
    return {
        "ok": True,
        "report": report,
        "detections": detections,
        "created_tasks": created,
        "executed_tasks": executed,
        "queue": queue_rows[:20],
        "queue_counts": _task_state_counts(queue_rows),
        "state": state_payload,
    }


def _load_task_queue(workspace) -> list[dict]:
    payload = _pref_value(workspace, TASK_QUEUE_PREF_KEY, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)][:120]


def _store_task_queue(workspace, rows: list[dict]):
    if not workspace:
        return
    cleaned = [row for row in (rows or []) if isinstance(row, dict)][:120]
    _store_pref_value(workspace, TASK_QUEUE_PREF_KEY, cleaned)


def _queue_signature(task: dict) -> str:
    if not isinstance(task, dict):
        return ""
    return "|".join([
        str(task.get("detector") or "").strip(),
        str(task.get("runbook") or "").strip(),
        str(task.get("title") or "").strip(),
    ])[:240]


def _task_state_counts(rows: list[dict]) -> dict:
    counts = {"pending": 0, "running": 0, "completed": 0, "blocked": 0}
    for row in rows or []:
        state = str((row or {}).get("status") or "").strip().lower()
        if state in counts:
            counts[state] += 1
    return counts


def _new_task_entry(*, detector: str, title: str, summary: str, severity: str, runbook: str, task_kind: str, tools: list[str], source: str, question: str = "", auto_execute: bool = False) -> dict:
    task_id = f"guard-task-{int(time.time() * 1000)}-{abs(hash((detector, title, summary))) % 100000}"
    row = {
        "id": task_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "detector": str(detector or "").strip()[:64],
        "title": _truncate(title, 160),
        "summary": _truncate(summary, 280),
        "severity": str(severity or "warning").strip()[:24],
        "runbook": str(runbook or "silent_diagnostics").strip()[:64],
        "task_kind": str(task_kind or "diagnose").strip()[:32],
        "tools": [str(x) for x in (tools or []) if str(x or "").strip()][:6],
        "source": str(source or "manual").strip()[:32],
        "question": _truncate(question, 220),
        "status": "pending",
        "auto_execute": bool(auto_execute),
        "executions": [],
        "result_summary": "",
        "signature": "",
    }
    row["signature"] = _queue_signature(row)
    return row


def _enqueue_task(workspace, task: dict) -> dict:
    if not workspace or not isinstance(task, dict):
        return task or {}
    rows = _load_task_queue(workspace)
    signature = _queue_signature(task)
    for row in rows:
        if str(row.get("signature") or "") == signature and str(row.get("status") or "") in {"pending", "running"}:
            return row
    rows.insert(0, dict(task, signature=signature))
    _store_task_queue(workspace, rows)
    return rows[0]


def _update_task_entry(workspace, task_id: str, **changes) -> dict | None:
    if not workspace or not task_id:
        return None
    rows = _load_task_queue(workspace)
    updated = None
    for idx, row in enumerate(rows):
        if str(row.get("id") or "") != str(task_id):
            continue
        merged = dict(row)
        merged.update(changes or {})
        merged["updated_at"] = _now_iso()
        rows[idx] = merged
        updated = merged
        break
    if updated is not None:
        _store_task_queue(workspace, rows)
    return updated


def _load_proactive_state(workspace) -> dict:
    payload = _pref_value(workspace, PROACTIVE_STATE_PREF_KEY, {})
    return payload if isinstance(payload, dict) else {}


def _store_proactive_state(workspace, payload: dict):
    if not workspace:
        return
    _store_pref_value(workspace, PROACTIVE_STATE_PREF_KEY, payload if isinstance(payload, dict) else {})

def _memory_pref_key(actor_id=None) -> str:
    if actor_id:
        return f"{MEMORY_PREF_KEY}:user:{int(actor_id)}"
    return MEMORY_PREF_KEY


def _normalize_memory_payload(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    return {
        "summary": str(payload.get("summary") or "").strip()[:1200],
        "recent_issues": [str(x) for x in (payload.get("recent_issues") or []) if str(x or "").strip()][:12],
        "recent_actions": [str(x) for x in (payload.get("recent_actions") or []) if str(x or "").strip()][:12],
        "recent_successes": [str(x) for x in (payload.get("recent_successes") or []) if str(x or "").strip()][:12],
        "recent_questions": [str(x) for x in (payload.get("recent_questions") or []) if str(x or "").strip()][:10],
        "recent_pages": [str(x) for x in (payload.get("recent_pages") or []) if str(x or "").strip()][:8],
        "last_status": str(payload.get("last_status") or "").strip()[:32],
        "last_error": str(payload.get("last_error") or "").strip()[:200],
        "turn_count": _safe_int(payload.get("turn_count"), 0),
        "last_updated": str(payload.get("last_updated") or "").strip()[:64],
    }


def _load_memory_for_actor(workspace, actor_id=None) -> dict:
    payload = _pref_value(workspace, _memory_pref_key(actor_id), {})
    return _normalize_memory_payload(payload)


def _merge_memory(global_memory: dict, actor_memory: dict) -> dict:
    merged = dict(global_memory or {})
    actor_memory = actor_memory or {}
    for key in ("summary", "last_status", "last_error", "last_updated"):
        if actor_memory.get(key):
            merged[key] = actor_memory.get(key)
    merged["turn_count"] = max(_safe_int(global_memory.get("turn_count") if isinstance(global_memory, dict) else 0, 0), _safe_int(actor_memory.get("turn_count"), 0))
    for key, limit in (("recent_issues", 12), ("recent_actions", 12), ("recent_successes", 12), ("recent_questions", 10), ("recent_pages", 8)):
        values = []
        seen = set()
        for source in (actor_memory.get(key) or [], global_memory.get(key) if isinstance(global_memory, dict) else []):
            for item in source or []:
                text = str(item or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                values.append(text)
                if len(values) >= limit:
                    break
            if len(values) >= limit:
                break
        merged[key] = values
    return _normalize_memory_payload(merged)


def _load_memory(workspace) -> dict:
    payload = _pref_value(workspace, MEMORY_PREF_KEY, {})
    return _normalize_memory_payload(payload)


def _store_memory(workspace, *, report: dict, response: dict, executed_tools: list[dict], question: str = "", page_context: dict | None = None, actor_id=None):
    if not workspace:
        return
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    current = _load_memory_for_actor(workspace, actor_id=actor_id)
    action_labels = [str(row.get("label") or row.get("tool") or "").strip() for row in executed_tools if isinstance(row, dict)]
    issue_labels = [str(row.get("id") or "").strip() for row in issues[:8] if isinstance(row, dict)]
    success_labels = [str(row.get("tool") or "").strip() for row in executed_tools if isinstance(row, dict) and row.get("ok")]
    message = _truncate(response.get("message"), 280)
    page_label = ""
    if isinstance(page_context, dict):
        page_label = str(page_context.get("title") or page_context.get("page") or page_context.get("path") or "").strip()[:160]
    payload = {
        "summary": _truncate(
            f"{message} Blockers {summary.get('blockers', 0)} · warnings {summary.get('warnings', 0)}.",
            1100,
        ),
        "recent_issues": (issue_labels + current.get("recent_issues", []))[:12],
        "recent_actions": ([x for x in action_labels if x] + current.get("recent_actions", []))[:12],
        "recent_successes": ([x for x in success_labels if x] + current.get("recent_successes", []))[:12],
        "recent_questions": ([str(question).strip()[:220]] if str(question or "").strip() else []) + current.get("recent_questions", []),
        "recent_pages": ([page_label] if page_label else []) + current.get("recent_pages", []),
        "last_status": str(response.get("status") or "").strip()[:32],
        "last_error": str(response.get("degraded_reason") or response.get("confirmation_text") or "")[:200],
        "turn_count": _safe_int(current.get("turn_count"), 0) + 1,
        "last_updated": _now_iso(),
    }
    payload = _normalize_memory_payload(payload)
    _store_pref_value(workspace, _memory_pref_key(actor_id), payload)
    if actor_id:
        global_current = _load_memory(workspace)
        global_payload = {
            "summary": payload.get("summary"),
            "recent_issues": (payload.get("recent_issues", []) + global_current.get("recent_issues", []))[:12],
            "recent_actions": (payload.get("recent_actions", []) + global_current.get("recent_actions", []))[:12],
            "recent_successes": (payload.get("recent_successes", []) + global_current.get("recent_successes", []))[:12],
            "recent_questions": (payload.get("recent_questions", []) + global_current.get("recent_questions", []))[:10],
            "recent_pages": (payload.get("recent_pages", []) + global_current.get("recent_pages", []))[:8],
            "last_status": payload.get("last_status"),
            "last_error": payload.get("last_error"),
            "turn_count": _safe_int(global_current.get("turn_count"), 0) + 1,
            "last_updated": payload.get("last_updated"),
        }
        _store_pref_value(workspace, MEMORY_PREF_KEY, _normalize_memory_payload(global_payload))


def _update_metrics(workspace, *, report: dict, response: dict, llm_used: bool, llm_ok: bool, executed_tools: list[dict], latency_ms: int):
    if not workspace:
        return
    payload = _pref_value(workspace, METRICS_PREF_KEY, {})
    if not isinstance(payload, dict):
        payload = {}
    total = _safe_int(payload.get("turns"), 0) + 1
    degraded = _safe_int(payload.get("degraded_turns"), 0) + (0 if llm_ok or not llm_used else 1)
    executed = _safe_int(payload.get("executed_tools"), 0) + len([x for x in executed_tools if isinstance(x, dict)])
    confirmations = _safe_int(payload.get("confirmations"), 0) + (1 if response.get("needs_confirmation") else 0)
    snapshot = {
        "turns": total,
        "degraded_turns": degraded,
        "executed_tools": executed,
        "confirmations": confirmations,
        "last_latency_ms": int(latency_ms or 0),
        "last_status": str(response.get("status") or "").strip()[:32],
        "last_issue_summary": report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {},
        "last_updated": _now_iso(),
    }
    _store_pref_value(workspace, METRICS_PREF_KEY, snapshot)


def _run_management_command(command_name: str, **kwargs) -> dict:
    stdout = StringIO()
    stderr = StringIO()
    try:
        call_command(command_name, stdout=stdout, stderr=stderr, verbosity=1, **kwargs)
        return {
            "ok": True,
            "command": command_name,
            "kwargs": kwargs,
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }
    except SystemExit as exc:
        code = _safe_int(exc.code, 1)
        return {
            "ok": False,
            "command": command_name,
            "kwargs": kwargs,
            "exit_code": code,
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }
    except Exception as exc:
        return {
            "ok": False,
            "command": command_name,
            "kwargs": kwargs,
            "error": f"{exc.__class__.__name__}: {exc}",
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }


def _run_management_smoke(command_name: str, *, verbosity: int = 1) -> dict:
    return _run_management_command(command_name, verbosity=verbosity)


def _operator_repo_path() -> Path | None:
    raw = str(os.getenv("OLLANA_OPERATOR_REPO_PATH") or settings.BASE_DIR).strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        return None
    if (path / ".git").exists():
        return path
    return None


def _run_repo_command(args: list[str], *, timeout: int = 120) -> dict:
    repo_path = _operator_repo_path()
    if repo_path is None:
        return {"ok": False, "error": "repo_not_available"}
    try:
        completed = subprocess.run(
            args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout or 120)),
        )
    except Exception as exc:
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}", "command": args}
    return {
        "ok": completed.returncode == 0,
        "command": args,
        "cwd": str(repo_path),
        "exit_code": int(completed.returncode or 0),
        "stdout": str(completed.stdout or "")[-8000:],
        "stderr": str(completed.stderr or "")[-4000:],
    }


def _extract_commit_message(question: str) -> str:
    text = str(question or "").strip()
    explicit = re.search(r"mensaje(?:\s+de\s+commit)?\s*[:=]\s*(.+)$", text, re.IGNORECASE)
    if explicit:
        value = _truncate(explicit.group(1), 120).strip(" \"'")
        if value:
            return value
    quoted = re.search(r'commit(?:\s+y\s+push|\s+y\s+publica|\s+push)?\s+["“](.+?)["”]', text, re.IGNORECASE)
    if quoted:
        value = _truncate(quoted.group(1), 120).strip()
        if value:
            return value
    slug = _truncate(re.sub(r"\s+", " ", text), 72)
    if slug:
        return f"Ollana operator: {slug}"
    return "Ollana operator update"


def _inspect_repo_status() -> dict:
    status = _run_repo_command(["git", "status", "--short", "--branch"], timeout=30)
    if not status.get("ok"):
        return status
    last = _run_repo_command(["git", "log", "-1", "--oneline"], timeout=30)
    branch = ""
    lines = [str(row) for row in str(status.get("stdout") or "").splitlines()]
    if lines and lines[0].startswith("##"):
        branch = lines[0][2:].strip()
    changed = [row for row in lines[1:] if str(row).strip()]
    return {
        "ok": True,
        "repo_path": status.get("cwd"),
        "branch": branch,
        "changed_files": changed[:80],
        "changed_count": len(changed),
        "last_commit": _truncate(last.get("stdout") or "", 200),
    }


def _run_operator_validation() -> dict:
    check = _run_management_command("check")
    check["action"] = "operator_validation"
    return check


def _git_commit_changes(question: str) -> dict:
    repo_path = _operator_repo_path()
    if repo_path is None:
        return {"ok": False, "error": "repo_not_available"}
    status = _inspect_repo_status()
    if not status.get("ok"):
        return status
    if not status.get("changed_count"):
        return {"ok": False, "error": "no_changes_to_commit", "repo_path": str(repo_path)}
    add_result = _run_repo_command(["git", "add", "-A"], timeout=60)
    if not add_result.get("ok"):
        add_result["action"] = "git_add"
        return add_result
    commit_message = _extract_commit_message(question)
    commit_result = _run_repo_command(["git", "commit", "-m", commit_message], timeout=120)
    commit_result["action"] = "git_commit"
    commit_result["commit_message"] = commit_message
    return commit_result


def _git_push_changes() -> dict:
    remote = str(os.getenv("OLLANA_OPERATOR_GIT_REMOTE") or "origin").strip() or "origin"
    branch = str(os.getenv("OLLANA_OPERATOR_GIT_BRANCH") or "main").strip() or "main"
    result = _run_repo_command(["git", "push", remote, f"HEAD:{branch}"], timeout=180)
    result["action"] = "git_push"
    result["remote"] = remote
    result["branch"] = branch
    return result


def _autofix_create_path(target_path: str) -> dict:
    path = Path(str(target_path or "").strip())
    if not str(path):
        return {"ok": False, "error": "empty_path"}
    try:
        path.mkdir(parents=True, exist_ok=True)
        return {"ok": path.exists(), "path": str(path)}
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": f"{exc.__class__.__name__}: {exc}"}


def _autofix_regenerate_task_previews() -> dict:
    result = _run_management_command("regenerate_task_previews", only="sessions", limit=12, force=True)
    result["action"] = "regenerate_task_previews"
    return result


def _autofix_ai_trainer_reindex() -> dict:
    result = _run_management_command("ai_trainer_reindex", limit=120, force=True)
    result["action"] = "ai_trainer_reindex"
    return result


def _autofix_ollama_pull(model_name: str) -> dict:
    model = str(model_name or "").strip()
    if not model:
        return {"ok": False, "error": "empty_model"}
    cfg = local_llm_config()
    body = json.dumps({"name": model, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{str(cfg.get('base_url') or '').rstrip('/')}/api/pull",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(10, _safe_int(cfg.get("timeout"), 45))) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        return {"ok": True, "action": "ollama_pull", "model": model, "detail": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "action": "ollama_pull", "model": model, "error": f"ollama_http_{exc.code}"}
    except Exception as exc:
        return {"ok": False, "action": "ollama_pull", "model": model, "error": f"{exc.__class__.__name__}: {exc}"}


def collect_system_guard_evidence(*, run_smoke: bool = False, smoke_verbosity: int = 1, page_context=None, memory=None) -> dict:
    health = run_system_healthcheck()
    inventory = _module_inventory()
    route_inventory = _route_inventory()
    asset_inventory = _asset_inventory()
    cfg = local_llm_config()
    probe = _probe_ollama(cfg)
    availability = _availability_snapshot(cfg, probe)
    evidence = {
        "environment": _environment_snapshot(),
        "healthcheck": health,
        "module_inventory": inventory,
        "route_inventory": route_inventory,
        "asset_inventory": asset_inventory,
        "tool_catalog": _tool_catalog(),
        "page_context": dict(page_context or {}),
        "memory": dict(memory or {}),
        "local_llm": {
            "enabled": bool(cfg.get("enabled")),
            "provider": str(cfg.get("provider") or ""),
            "model": str(cfg.get("model") or ""),
            "base_url": str(cfg.get("base_url") or ""),
            "timeout": _safe_int(cfg.get("timeout"), 0),
            "probe": probe,
            "availability": availability,
        },
        "smoke": {
            "requested": bool(run_smoke),
            "results": {},
        },
    }
    if run_smoke:
        for key in ("django_smoke", "system_suite"):
            cmd = str(MODULE_SMOKE_MAP[key]["command"])
            evidence["smoke"]["results"][key] = _run_management_smoke(cmd, verbosity=smoke_verbosity)
    return evidence


def _issue(issue_id: str, *, severity: str, area: str, message: str, detail=None, autofix=False, autofix_key: str = "", repairable=False) -> dict:
    return {
        "id": issue_id,
        "severity": severity,
        "area": area,
        "message": message,
        "detail": detail,
        "autofix": bool(autofix),
        "autofix_key": str(autofix_key or ""),
        "repairable": bool(repairable or autofix),
    }


def _derive_issues(evidence: dict) -> list[dict]:
    issues = []
    health = evidence.get("healthcheck") if isinstance(evidence.get("healthcheck"), dict) else {}
    db = health.get("database") if isinstance(health.get("database"), dict) else {}
    if not db.get("ok"):
        issues.append(_issue("database_unhealthy", severity="blocker", area="database", message="La base de datos no responde correctamente.", detail=db.get("detail")))
    for key, item in (health.get("paths") or {}).items():
        if isinstance(item, dict) and not item.get("ok"):
            path_value = str(item.get("detail") or item.get("path") or "")
            issues.append(
                _issue(
                    f"path_missing_{key}",
                    severity="warning",
                    area="filesystem",
                    message=f"Falta la ruta crítica {key}.",
                    detail=path_value,
                    autofix=bool(path_value),
                    autofix_key=f"create_path:{path_value}" if path_value else "",
                )
            )
    for key, item in (health.get("dependencies") or {}).items():
        if isinstance(item, dict) and not item.get("ok"):
            issues.append(_issue(f"dependency_{key}", severity="warning", area="dependencies", message=f"La dependencia {key} no está operativa.", detail=item.get("detail")))
    for key, item in (evidence.get("module_inventory") or {}).items():
        if isinstance(item, dict) and item.get("kind") == "script" and not item.get("exists"):
            issues.append(_issue(f"missing_script_{key}", severity="warning", area="coverage", message=f"Falta el smoke script del módulo {key}.", detail=item.get("path")))
    for key, item in (evidence.get("route_inventory") or {}).items():
        if isinstance(item, dict) and not item.get("ok"):
            issues.append(_issue(f"missing_route_{key}", severity="blocker", area="routing", message=f"Falta o no resuelve la ruta crítica {key}.", detail=item.get("error") or item.get("name")))
    for key, item in (evidence.get("asset_inventory") or {}).items():
        if isinstance(item, dict) and not item.get("ok"):
            issues.append(_issue(f"missing_asset_{key}", severity="blocker", area="assets", message=f"Falta el asset crítico {key}.", detail=item.get("path")))
    llm = evidence.get("local_llm") if isinstance(evidence.get("local_llm"), dict) else {}
    availability = llm.get("availability") if isinstance(llm.get("availability"), dict) else {}
    probe = llm.get("probe") if isinstance(llm.get("probe"), dict) else {}
    if llm.get("enabled") and availability.get("state") == "down":
        issues.append(_issue("ollama_unreachable", severity="warning", area="local_llm", message="Ollama está configurado pero no responde.", detail=probe.get("error")))
    elif llm.get("enabled") and availability.get("state") == "degraded":
        issues.append(
            _issue(
                "ollama_model_missing",
                severity="warning",
                area="local_llm",
                message="Ollama responde pero el modelo configurado no está cargado.",
                detail=probe.get("model"),
                autofix=True,
                autofix_key=f"ollama_pull:{probe.get('model')}",
            )
        )
    smoke = evidence.get("smoke") if isinstance(evidence.get("smoke"), dict) else {}
    for key, item in (smoke.get("results") or {}).items():
        if isinstance(item, dict) and not item.get("ok"):
            issues.append(_issue(f"smoke_failed_{key}", severity="blocker", area="smoke", message=f"Ha fallado el smoke {key}.", detail=item.get("error") or item.get("exit_code") or item.get("stderr") or item.get("stdout")))
    return issues


def _apply_autofix(issue: dict) -> dict:
    autofix_key = str(issue.get("autofix_key") or "").strip()
    if not autofix_key:
        return {"ok": False, "issue_id": issue.get("id"), "error": "missing_autofix_key"}
    if autofix_key.startswith("create_path:"):
        result = _autofix_create_path(autofix_key.split(":", 1)[1])
        result["issue_id"] = issue.get("id")
        result["action"] = "create_path"
        return result
    if autofix_key.startswith("ollama_pull:"):
        result = _autofix_ollama_pull(autofix_key.split(":", 1)[1])
        result["issue_id"] = issue.get("id")
        return result
    return {"ok": False, "issue_id": issue.get("id"), "error": "unsupported_autofix"}


def _apply_autofixes(issues: list[dict]) -> dict:
    applied = []
    skipped = []
    for issue in issues or []:
        if not issue.get("autofix"):
            skipped.append({"issue_id": issue.get("id"), "reason": "not_autofixable"})
            continue
        result = _apply_autofix(issue)
        (applied if result.get("ok") else skipped).append(result)
    return {"applied": applied, "skipped": skipped}


def _run_named_maintenance_action(action_name: str) -> dict:
    action = str(action_name or "").strip()
    if action == "regenerate_task_previews":
        return _autofix_regenerate_task_previews()
    if action == "ai_trainer_reindex":
        return _autofix_ai_trainer_reindex()
    return {"ok": False, "error": "unknown_maintenance_action", "action": action}


def _severity_rank(value: str) -> int:
    return {"info": 0, "warning": 1, "blocker": 2}.get(str(value or "").lower(), 0)


def _base_ok_from_issues(issues: list[dict]) -> bool:
    return not any(_severity_rank(issue.get("severity")) >= 2 for issue in (issues or []))


def _base_status_from_issues(issues: list[dict]) -> str:
    if any(_severity_rank(issue.get("severity")) >= 2 for issue in issues or []):
        return "fail"
    if issues:
        return "watch"
    return "ok"


def _compact_evidence_for_llm(evidence: dict, issues: list[dict], memory: dict | None = None) -> dict:
    health = evidence.get("healthcheck") if isinstance(evidence.get("healthcheck"), dict) else {}
    smoke = evidence.get("smoke") if isinstance(evidence.get("smoke"), dict) else {}
    return {
        "environment": evidence.get("environment"),
        "page_context": evidence.get("page_context"),
        "memory": memory or evidence.get("memory"),
        "healthcheck": {
            "database": health.get("database"),
            "paths": {k: v for k, v in (health.get("paths") or {}).items() if isinstance(v, dict) and not v.get("ok")},
            "dependencies": {k: v for k, v in (health.get("dependencies") or {}).items() if isinstance(v, dict) and not v.get("ok")},
        },
        "route_inventory": {k: v for k, v in (evidence.get("route_inventory") or {}).items() if isinstance(v, dict) and not v.get("ok")},
        "asset_inventory": {k: v for k, v in (evidence.get("asset_inventory") or {}).items() if isinstance(v, dict) and not v.get("ok")},
        "local_llm": evidence.get("local_llm"),
        "tool_catalog": evidence.get("tool_catalog"),
        "smoke_failures": {k: v for k, v in (smoke.get("results") or {}).items() if isinstance(v, dict) and not v.get("ok")},
        "issues": issues or [],
    }


def build_system_guard_prompt(evidence: dict, issues: list[dict], memory: dict | None = None) -> str:
    payload = json.dumps(_compact_evidence_for_llm(evidence, issues, memory=memory), ensure_ascii=False, separators=(",", ":"))
    return (
        "Eres un revisor senior de fiabilidad para una plataforma SaaS de fútbol. "
        "Analiza solo el JSON recibido y devuelve solo JSON válido con estas claves exactas: "
        "overall_status:string, blockers:list, warnings:list, prevention_actions:list, watch_modules:list, autofix_candidates:list, summary:string. "
        "overall_status debe ser ok, watch, risk o fail. "
        "En español, breve y técnico.\n\n"
        f"EVIDENCE_JSON={payload}"
    )


def build_system_guard_chat_prompt(report: dict, question: str, history=None, planner=None, memory=None, audience: str = "technical") -> str:
    payload = json.dumps(
        {
            "question": _truncate(question, 3000),
            "history": [row for row in (history or [])[-8:] if isinstance(row, dict)],
            "planner": planner or {},
            "memory": memory or {},
            "audience": audience,
            "report": {
                "ok": bool(report.get("ok")),
                "issue_summary": report.get("issue_summary"),
                "issues": report.get("issues"),
                "compact_evidence": _compact_evidence_for_llm(
                    report.get("evidence") if isinstance(report.get("evidence"), dict) else {},
                    report.get("issues") if isinstance(report.get("issues"), list) else [],
                    memory=memory or {},
                ),
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "Eres el Guardián del sistema de una plataforma SaaS de fútbol. "
        "Debes responder solo con JSON válido con estas claves exactas: "
        "status:string, message:string, highlights:list, actions:list. "
        "status debe ser ok, watch, risk o fail. "
        "actions debe listar objetos {label, reason}. "
        "Usa solo el JSON recibido. Escribe en español.\n\n"
        f"CHAT_GUARD_JSON={payload}"
    )


def _history_tail(history) -> list[dict]:
    rows = []
    for row in (history or [])[-8:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        content = str(row.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            rows.append({"role": role, "content": _truncate(content, 1200)})
    return rows


def _extract_labeled_value(question: str, labels: list[str]) -> str:
    text = str(question or "")
    if not text or not labels:
        return ""
    joined = "|".join(re.escape(str(label or "").strip()) for label in labels if str(label or "").strip())
    if not joined:
        return ""
    match = re.search(rf"(?:{joined})\s*[:=]?\s*([^,;\n]+)", text, re.IGNORECASE)
    return str(match.group(1) if match else "").strip(" .")


def _parse_player_request(question: str) -> dict:
    text = str(question or "").strip()
    lower = text.lower()
    name = _extract_labeled_value(text, ["nombre", "player"])
    if not name:
        free_name = re.search(
            r"(?:introduce|añade|agrega|crea|alta(?:\s+de)?|incorpora)\s+(?:un\s+)?jugador(?:\s+en\s+plantilla)?\s+(.+?)(?=,| con | dorsal| numero| número| posicion| posición| pie| altura| peso| nacimiento| fecha|$)",
            text,
            re.IGNORECASE,
        )
        name = str(free_name.group(1) if free_name else "").strip(" .")
    number_raw = _extract_labeled_value(text, ["dorsal", "numero", "número", "nº", "num"])
    position = _extract_labeled_value(text, ["posicion", "posición", "puesto"])
    preferred_position = _extract_labeled_value(text, ["posicion preferida", "posición preferida", "preferred_position"])
    dominant_foot = _extract_labeled_value(text, ["pie", "pie dominante", "dominant_foot"])
    height_raw = _extract_labeled_value(text, ["altura", "height"])
    weight_raw = _extract_labeled_value(text, ["peso", "weight"])
    birth_raw = _extract_labeled_value(text, ["fecha nacimiento", "nacimiento", "birth_date"])
    full_name = _extract_labeled_value(text, ["nombre completo", "full_name"])
    nickname = _extract_labeled_value(text, ["apodo", "nickname"])
    origin_team = _extract_labeled_value(text, ["equipo origen", "origen", "origin_team"])
    is_active = True
    if re.search(r"\b(inactivo|baja|desactivar)\b", lower):
        is_active = False

    number = _safe_int(number_raw, 0) if number_raw else None
    if number == 0:
        number = None
    height_cm = _safe_int(re.sub(r"[^\d]", "", height_raw), 0) if height_raw else None
    if height_cm == 0:
        height_cm = None
    weight_value = ""
    if weight_raw:
        match = re.search(r"\d+(?:[.,]\d+)?", weight_raw)
        weight_value = str(match.group(0) if match else "").replace(",", ".")
    birth_date = None
    if birth_raw:
        match = re.search(r"\d{4}-\d{2}-\d{2}", birth_raw)
        if match:
            try:
                birth_date = datetime.strptime(match.group(0), "%Y-%m-%d").date()
            except ValueError:
                birth_date = None
    return {
        "name": _truncate(name, 120),
        "full_name": _truncate(full_name, 180),
        "nickname": _truncate(nickname, 80),
        "number": number,
        "position": _truncate(position, 60),
        "preferred_position": _truncate(preferred_position, 60),
        "dominant_foot": _truncate(dominant_foot, 16),
        "height_cm": height_cm,
        "weight_kg": weight_value[:16],
        "birth_date": birth_date,
        "origin_team": _truncate(origin_team, 160),
        "is_active": bool(is_active),
    }


def _active_workspace_season(workspace):
    if not workspace:
        return None
    season = getattr(workspace, "active_season", None)
    if season:
        return season
    return WorkspaceSeason.objects.filter(workspace=workspace, is_active=True).order_by("-start_date", "-id").first()


def _execute_create_player_action(question: str, *, workspace=None, page_context=None) -> dict:
    page_context = page_context if isinstance(page_context, dict) else {}
    payload = _parse_player_request(question)
    if not workspace:
        return {
            "kind": "create_player",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": ["contexto_equipo"],
            "message": "No puedo crear el jugador sin un workspace activo.",
            "payload": payload,
        }
    if not bool(page_context.get("can_manage_guard")):
        return {
            "kind": "create_player",
            "executed": False,
            "success": False,
            "needs_input": False,
            "permission_required": True,
            "message": "Necesitas permisos de gestión para modificar la plantilla.",
            "payload": payload,
        }
    team_id = _safe_int(page_context.get("team_id"), 0)
    team = None
    if team_id and getattr(workspace, "teams", None) is not None:
        link = workspace.teams.select_related("team").filter(team_id=team_id).first()
        team = getattr(link, "team", None) if link else None
    if team is None:
        team = getattr(workspace, "primary_team", None)
    if not team:
        return {
            "kind": "create_player",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": ["equipo"],
            "message": "No encuentro el equipo activo para dar de alta al jugador.",
            "payload": payload,
        }
    try:
        WorkspaceTeam.objects.get_or_create(workspace=workspace, team=team, defaults={"is_default": True})
    except Exception:
        pass
    missing_fields = []
    if not payload.get("name"):
        missing_fields.append("nombre")
    if missing_fields:
        return {
            "kind": "create_player",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": missing_fields,
            "message": "Pásame al menos el nombre del jugador para crear la ficha.",
            "payload": payload,
        }

    with transaction.atomic():
        player = Player.objects.filter(team=team, name__iexact=str(payload.get("name") or "")).order_by("id").first()
        created = player is None
        if created:
            player = Player.objects.create(
                team=team,
                name=str(payload.get("name") or "")[:120],
                full_name=str(payload.get("full_name") or "")[:180],
                nickname=str(payload.get("nickname") or "")[:80],
                birth_date=payload.get("birth_date"),
                height_cm=payload.get("height_cm"),
                weight_kg=(payload.get("weight_kg") or None),
                origin_team=str(payload.get("origin_team") or "")[:160],
                dominant_foot=str(payload.get("dominant_foot") or "")[:16],
                preferred_position=str(payload.get("preferred_position") or "")[:60],
                number=payload.get("number"),
                position=str(payload.get("position") or "")[:60],
                is_active=bool(payload.get("is_active")),
            )
        else:
            updated_fields = []
            for field in ("full_name", "nickname", "birth_date", "height_cm", "origin_team", "dominant_foot", "preferred_position", "number", "position"):
                value = payload.get(field)
                if value in ("", None) and field not in {"number", "birth_date", "height_cm"}:
                    continue
                if getattr(player, field) != value:
                    setattr(player, field, value)
                    updated_fields.append(field)
            weight_value = payload.get("weight_kg") or None
            if getattr(player, "weight_kg") != weight_value:
                player.weight_kg = weight_value
                updated_fields.append("weight_kg")
            is_active = bool(payload.get("is_active"))
            if bool(getattr(player, "is_active", True)) != is_active:
                player.is_active = is_active
                updated_fields.append("is_active")
            if updated_fields:
                player.save(update_fields=sorted(set(updated_fields)))

        ensure_workspace_player(workspace, player, current_team=team, is_active=bool(payload.get("is_active")))
        season = _active_workspace_season(workspace)
        if season:
            ensure_player_season_membership(
                season,
                player,
                team=team,
                confirmed=False,
                status=("pending" if bool(payload.get("is_active")) else "inactive"),
            )

    return {
        "kind": "create_player",
        "executed": True,
        "success": True,
        "needs_input": False,
        "message": (
            f"Jugador añadido a la plantilla: {player.name}."
            if created else f"Jugador actualizado en plantilla: {player.name}."
        ),
        "player": {
            "id": int(getattr(player, "id", 0) or 0),
            "name": str(getattr(player, "name", "") or ""),
            "team": str(getattr(team, "name", "") or ""),
            "number": getattr(player, "number", None),
            "position": str(getattr(player, "position", "") or ""),
        },
        "payload": payload,
    }


def _build_improvement_proposals(report: dict, *, page_context=None, workspace=None) -> list[dict]:
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    blockers = _safe_int(summary.get("blockers"), 0)
    warnings = _safe_int(summary.get("warnings"), 0)
    page = str((page_context or {}).get("page") or "").strip()
    queue_counts = _task_state_counts(_load_task_queue(workspace)) if workspace else {"pending": 0, "running": 0, "completed": 0, "blocked": 0}
    proposals = []
    if blockers > 0:
        proposals.append({
            "title": "Cerrar blockers antes de ampliar funcionalidad",
            "reason": f"Hay {blockers} blocker(s) activos; conviene priorizar estabilidad del sistema.",
            "priority": "high",
            "kind": "stability",
        })
    if warnings > 0:
        proposals.append({
            "title": "Reducir warnings recurrentes",
            "reason": f"Se mantienen {warnings} warning(s); Ollana puede vigilar regresiones y consolidar remediaciones.",
            "priority": "medium",
            "kind": "observability",
        })
    if queue_counts.get("pending", 0) == 0 and queue_counts.get("running", 0) == 0:
        proposals.append({
            "title": "Programar ciclo proactivo continuo",
            "reason": "No hay tareas silenciosas en cola; conviene mantener inspección continua con runbooks proactivos.",
            "priority": "medium",
            "kind": "automation",
        })
    if page in {"dashboard-home", "coach-role-trainer"}:
        proposals.append({
            "title": "Añadir accesos guiados por lenguaje natural",
            "reason": "La portada es el mejor punto para comandos rápidos tipo “llévame a vídeo análisis” o “abre biblioteca de tareas”.",
            "priority": "medium",
            "kind": "ux",
        })
    proposals.append({
        "title": "Ampliar acciones asistidas con formularios mínimos",
        "reason": "El siguiente salto es cubrir altas de jugadores, creación de sesiones y apertura de módulos desde una sola caja conversacional.",
        "priority": "next",
        "kind": "assistant",
    })
    return proposals[:4]


def _resolve_assisted_action(question: str, *, workspace=None, page_context=None) -> dict:
    intent = _infer_intent(question)
    if intent == "create_player":
        return _execute_create_player_action(question, workspace=workspace, page_context=page_context)
    return {}


def _infer_intent(question: str) -> str:
    text = str(question or "").strip().lower()
    if re.search(r"\b(introduce|añade|agrega|crea|alta|incorpora)\b.*\b(jugador|player|plantilla|roster)\b", text):
        return "create_player"
    if re.search(r"\b(commit\s+y\s+push|haz\s+commit\s+y\s+push|publica\s+los?\s+cambios?|sube\s+los?\s+cambios?)\b", text):
        return "publish_commit_push"
    if re.search(r"\b(haz\s+commit|crea\s+commit|committea|commitea)\b", text):
        return "publish_commit"
    if re.search(r"\b(haz\s+push|sube\s+el\s+commit|publica\s+el\s+commit|push)\b", text):
        return "publish_push"
    if re.search(r"\b(repo|repositorio|git status|diff|working tree|arbol de trabajo)\b", text):
        return "inspect_repo"
    if re.search(r"\b(valida|validacion|valida cambios|ejecuta check|ejecuta tests?)\b", text):
        return "operator_validate"
    if re.search(r"\b(historial|histórico|historico|regresion|regresiones|tendencia|tendencias)\b", text):
        return "inspect_history"
    if re.search(r"\b(config|configuracion|settings|allowed_hosts|csrf|host)\b", text):
        return "inspect_config"
    if re.search(r"\b(path|paths|carpeta|carpetas|directorio|directorios|static|media)\b", text):
        return "inspect_paths"
    if re.search(r"\b(log|logs|error|errores|traceback|host|https)\b", text):
        return "inspect_errors"
    if re.search(r"\b(ruta|rutas|route|routes|endpoint|endpoints)\b", text):
        return "inspect_routes"
    if re.search(r"\b(preview|previews)\b", text):
        return "maintenance_previews"
    if re.search(r"\b(reindex|reindexa|reindexar)\b", text):
        return "maintenance_reindex"
    if re.search(r"\b(auto[\s-]?fix|arregla|corrige|repara)\b", text):
        return "repair"
    if re.search(r"\b(smoke|test|tests|suite)\b", text):
        return "diagnose_smoke"
    if re.search(r"\b(guia|explica|como|qué|que pasa|por qué|por que)\b", text):
        return "guide_user"
    return "diagnose_status"


def _tool_reason(tool_key: str, intent: str, question: str) -> str:
    mapping = {
        "inspect_repo_status": "La petición requiere revisar el estado actual del repositorio antes de publicar.",
        "run_operator_validation": "Conviene validar el proyecto antes de publicar cambios.",
        "git_commit": "La petición pide consolidar los cambios en un commit.",
        "git_push": "La petición pide publicar el commit en el remoto configurado.",
        "run_smoke": "El usuario pide validación operativa y conviene ejecutar smoke rápido.",
        "auto_fix": "El usuario pide corrección segura sobre incidencias conocidas.",
        "regenerate_task_previews": "La petición apunta a regenerar previews de tareas.",
        "ai_trainer_reindex": "La petición apunta a reindexar la base de IA-Trainer.",
        "check_status": "La petición requiere diagnóstico del estado actual.",
        "inspect_recent_errors": "La petición menciona errores, logs o síntomas recientes del sistema.",
        "check_critical_routes": "La petición pide revisar rutas o endpoints críticos.",
        "inspect_runtime_config": "La petición apunta a configuración efectiva de hosts, CSRF o settings.",
        "inspect_critical_paths": "La petición apunta a directorios y paths críticos del sistema.",
        "inspect_guard_history": "La petición pide comparar ejecuciones previas, regresiones o tendencias del guard.",
    }
    return mapping.get(tool_key, f"Acción seleccionada para la intención {intent} en: {_truncate(question, 80)}")


def _plan_tools(question: str, *, run_smoke: bool, auto_fix: bool, maintenance_action: str, autonomy_mode: str, page_context=None) -> dict:
    intent = _infer_intent(question)
    task = _build_task_profile(question, intent=intent, maintenance_action=maintenance_action, page_context=page_context)
    requested_tools = []
    steps = [{"step": "Diagnosticar estado base", "done": True}]
    if maintenance_action == "git_commit_push":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation", "git_commit", "git_push"])
    elif maintenance_action == "git_commit":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation", "git_commit"])
    elif maintenance_action == "git_push":
        requested_tools.extend(["inspect_repo_status", "git_push"])
    elif maintenance_action == "regenerate_task_previews":
        requested_tools.append("regenerate_task_previews")
    elif maintenance_action == "ai_trainer_reindex":
        requested_tools.append("ai_trainer_reindex")
    elif intent == "publish_commit_push":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation", "git_commit", "git_push"])
    elif intent == "publish_commit":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation", "git_commit"])
    elif intent == "publish_push":
        requested_tools.extend(["inspect_repo_status", "git_push"])
    elif intent == "inspect_repo":
        requested_tools.append("inspect_repo_status")
    elif intent == "operator_validate":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation"])
    elif auto_fix:
        requested_tools.append("auto_fix")
    elif run_smoke:
        requested_tools.append("run_smoke")
    elif intent == "maintenance_previews":
        requested_tools.append("regenerate_task_previews")
    elif intent == "maintenance_reindex":
        requested_tools.append("ai_trainer_reindex")
    elif intent == "repair":
        requested_tools.append("auto_fix")
    elif intent == "diagnose_smoke":
        requested_tools.append("run_smoke")
    elif intent == "inspect_errors":
        requested_tools.extend(["check_status", "inspect_recent_errors"])
    elif intent == "inspect_routes":
        requested_tools.extend(["check_status", "check_critical_routes"])
    elif intent == "inspect_config":
        requested_tools.extend(["check_status", "inspect_runtime_config"])
    elif intent == "inspect_paths":
        requested_tools.extend(["check_status", "inspect_critical_paths"])
    elif intent == "inspect_history":
        requested_tools.extend(["check_status", "inspect_guard_history"])
    elif intent == "diagnose_status":
        requested_tools.append("check_status")
    if intent == "guide_user" and "check_status" not in requested_tools:
        requested_tools.insert(0, "check_status")
    requested_tools = [tool for tool in requested_tools if tool in TOOL_SCHEMAS]
    if "auto_fix" in requested_tools and "check_status" not in requested_tools:
        requested_tools.insert(0, "check_status")
    if "run_smoke" in requested_tools and "check_status" not in requested_tools:
        requested_tools.insert(0, "check_status")
    if len(requested_tools) > 1 and "run_smoke" not in requested_tools and auto_fix:
        requested_tools.append("run_smoke")
    seen = set()
    deduped = []
    for tool in requested_tools:
        if tool in seen:
            continue
        seen.add(tool)
        deduped.append(tool)
    requested_tools = deduped[:4]
    tool_reasons = [{"tool": tool, "reason": _tool_reason(tool, intent, question)} for tool in requested_tools]
    for tool in requested_tools:
        steps.append({"step": f"Evaluar {TOOL_SCHEMAS.get(tool, {}).get('label') or tool}", "done": False})
    confirm_required = False
    confirm_text = ""
    sensitive = []
    if autonomy_mode == "supervised" and any(tool != "check_status" for tool in requested_tools):
        sensitive.extend([tool for tool in requested_tools if tool != "check_status"])
    sensitive.extend([tool for tool in requested_tools if TOOL_SCHEMAS.get(tool, {}).get("confirmation_required")])
    sensitive = list(dict.fromkeys(sensitive))
    if sensitive:
        confirm_required = True
        confirm_text = f"Confirmación requerida antes de ejecutar: {', '.join(sensitive)}."
    runbook = _runbook_payload(
        str(task.get("runbook_key") or "silent_diagnostics"),
        task=task,
        requested_tools=requested_tools,
        confirm_required=confirm_required,
    )
    followup_actions = _followup_actions(task, {"confirm_required": confirm_required, "confirmation_text": confirm_text}, page_context=page_context)
    return {
        "intent": intent,
        "task": task,
        "runbook": runbook,
        "requested_tools": requested_tools,
        "tool_reasons": tool_reasons,
        "steps": steps[:6],
        "confirm_required": confirm_required,
        "confirmation_text": confirm_text,
        "followup_actions": followup_actions,
    }


def _serialize_execution(tool_key: str, result: dict) -> dict:
    return {
        "tool": tool_key,
        "label": str(TOOL_SCHEMAS.get(tool_key, {}).get("label") or tool_key),
        "ok": bool(result.get("ok")),
        "kind": str(TOOL_SCHEMAS.get(tool_key, {}).get("kind") or ""),
        "detail": _truncate(result.get("error") or result.get("stderr") or result.get("stdout") or result.get("detail") or "", 320),
        "result": result,
    }


def _execute_tools(requested_tools: list[str], *, smoke_verbosity: int = 1, workspace=None, question: str = "") -> list[dict]:
    executions = []
    for tool_key in requested_tools or []:
        if tool_key == "check_status":
            result = {"ok": True, "action": "status_checked"}
        elif tool_key == "inspect_repo_status":
            result = _inspect_repo_status()
        elif tool_key == "run_operator_validation":
            result = _run_operator_validation()
        elif tool_key == "inspect_recent_errors":
            result = _inspect_recent_errors()
        elif tool_key == "check_critical_routes":
            result = _check_critical_routes()
        elif tool_key == "inspect_runtime_config":
            result = _inspect_runtime_config()
        elif tool_key == "inspect_critical_paths":
            result = _inspect_critical_paths()
        elif tool_key == "inspect_guard_history":
            result = _inspect_guard_history(workspace)
        elif tool_key == "run_smoke":
            result = _run_management_smoke("smoke", verbosity=smoke_verbosity)
        elif tool_key == "auto_fix":
            result = {"ok": True, "action": "autofix_requested"}
        elif tool_key == "regenerate_task_previews":
            result = _autofix_regenerate_task_previews()
        elif tool_key == "ai_trainer_reindex":
            result = _autofix_ai_trainer_reindex()
        elif tool_key == "git_commit":
            result = _git_commit_changes(question)
        elif tool_key == "git_push":
            result = _git_push_changes()
        else:
            result = {"ok": False, "error": "unsupported_tool"}
        executions.append(_serialize_execution(tool_key, result))
    return executions


def run_system_guard(*, run_smoke: bool = False, smoke_verbosity: int = 1, run_llm: bool = True, auto_fix: bool = False, page_context=None, memory=None) -> dict:
    initial_evidence = collect_system_guard_evidence(
        run_smoke=run_smoke,
        smoke_verbosity=smoke_verbosity,
        page_context=page_context,
        memory=memory,
    )
    initial_issues = _derive_issues(initial_evidence)
    autofix = {
        "requested": bool(auto_fix),
        "applied": [],
        "skipped": [],
        "reran_after_fix": False,
    }
    evidence = initial_evidence
    issues = initial_issues
    if auto_fix:
        fix_result = _apply_autofixes(initial_issues)
        autofix["applied"] = fix_result.get("applied") or []
        autofix["skipped"] = fix_result.get("skipped") or []
        if autofix["applied"]:
            autofix["reran_after_fix"] = True
            evidence = collect_system_guard_evidence(
                run_smoke=run_smoke,
                smoke_verbosity=smoke_verbosity,
                page_context=page_context,
                memory=memory,
            )
            issues = _derive_issues(evidence)
    report = {
        "ok": _base_ok_from_issues(issues),
        "issues": issues,
        "issue_summary": {
            "blockers": sum(1 for issue in issues if _severity_rank(issue.get("severity")) >= 2),
            "warnings": sum(1 for issue in issues if str(issue.get("severity") or "") == "warning"),
            "autofixable": sum(1 for issue in issues if issue.get("autofix")),
        },
        "autofix": autofix,
        "evidence": evidence,
        "llm_review": {
            "requested": bool(run_llm),
            "available": False,
            "error": "",
            "review": None,
        },
    }
    if not run_llm:
        return report
    cfg = local_llm_config()
    if not cfg.get("enabled") or str(cfg.get("provider") or "").lower() != "ollama":
        report["llm_review"]["error"] = "local_llm_disabled_or_unsupported"
        return report
    parsed, error = call_ollama_json(
        build_system_guard_prompt(evidence, issues, memory=memory or {}),
        model=cfg.get("model"),
        base_url=cfg.get("base_url"),
        timeout=cfg.get("timeout"),
    )
    report["llm_review"]["available"] = isinstance(parsed, dict)
    report["llm_review"]["error"] = str(error or "")
    report["llm_review"]["review"] = parsed if isinstance(parsed, dict) else None
    return report


def _fallback_actions(report: dict, executions: list[dict], planner: dict) -> list[dict]:
    actions = []
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    if summary.get("blockers"):
        actions.append({"label": "Resolver blockers", "reason": f"Hay {summary.get('blockers')} blocker(s) activos."})
    if summary.get("warnings"):
        actions.append({"label": "Revisar warnings", "reason": f"Hay {summary.get('warnings')} warning(s) activos."})
    for row in executions[:3]:
        if isinstance(row, dict):
            actions.append({"label": row.get("label"), "reason": "Acción ejecutada en esta conversación."})
    if planner.get("requested_tools") and not executions:
        for tool in planner.get("requested_tools")[:3]:
            actions.append({"label": str(TOOL_SCHEMAS.get(tool, {}).get("label") or tool), "reason": "Acción detectada como siguiente paso lógico."})
    return actions[:6]


def _known_fix_for_patterns(pattern_names: set[str], failing_routes: list[dict]) -> list[dict]:
    proposals = []
    if "DisallowedHost" in pattern_names:
        proposals.append(KNOWN_FIXES["DisallowedHost"])
    if "HTTPS_on_HTTP_devserver" in pattern_names:
        proposals.append(KNOWN_FIXES["HTTPS_on_HTTP_devserver"])
    if failing_routes:
        proposals.append(KNOWN_FIXES["missing_route"])
    return proposals[:4]


def _build_patch_proposals(report: dict, executions: list[dict]) -> list[dict]:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    issue_ids = {str(row.get("id") or "") for row in issues if isinstance(row, dict)}
    proposals = []
    if "path_missing_static_root" in issue_ids:
        proposals.append({
            "title": "Crear guardia para `static_root`",
            "files": ["webstats/settings.py", "render.yaml"],
            "summary": "Añadir verificación o creación segura de `STATIC_ROOT` en entornos locales/efímeros.",
            "dry_run": "Comprobar si `STATIC_ROOT` existe antes de dependencias que la usen y documentar el mount/creación en despliegue.",
        })
    if "ollama_unreachable" in issue_ids:
        proposals.append({
            "title": "Degradación explícita cuando Ollama cae",
            "files": ["football/system_guard.py", "football/local_llm.py"],
            "summary": "Reforzar el fallback y las señales de disponibilidad para no bloquear al usuario.",
            "dry_run": "Mantener respuesta útil sin `chat.response = null` y registrar latencia/caída de proveedor local.",
        })
    recent_errors = next((row.get("result") for row in executions if isinstance(row, dict) and row.get("tool") == "inspect_recent_errors"), {})
    patterns = recent_errors.get("patterns") if isinstance(recent_errors, dict) and isinstance(recent_errors.get("patterns"), list) else []
    pattern_names = {str(row.get("name") or "") for row in patterns if isinstance(row, dict)}
    if "DisallowedHost" in pattern_names:
        proposals.append({
            "title": "Normalizar hosts de desarrollo y despliegue",
            "files": ["webstats/settings.py"],
            "summary": "Blindar normalización de `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` para hosts controlados.",
            "dry_run": "Añadir cobertura para `testserver`, host público canónico y hosts de landing sin relajar producción.",
        })
    failing_routes = next((row.get("result", {}).get("failing") for row in executions if isinstance(row, dict) and row.get("tool") == "check_critical_routes"), [])
    if failing_routes:
        proposals.append({
            "title": "Reconstruir rutas críticas fallidas",
            "files": ["football/urls.py", "football/views.py"],
            "summary": "Alinear nombres de rutas y vistas para restaurar navegación crítica.",
            "dry_run": f"Revisar {len(failing_routes)} rutas marcadas por el guard y corregir `reverse`/imports asociados.",
        })
    return proposals[:6]


def _build_remediation_plan(report: dict, executions: list[dict], snapshot_diff: dict | None = None) -> dict:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    suggestions = []
    code_changes = []
    user_guidance = []
    issue_ids = {str(row.get("id") or "") for row in issues if isinstance(row, dict)}
    execution_map = {str(row.get("tool") or ""): row.get("result") for row in executions if isinstance(row, dict)}

    if "ollama_unreachable" in issue_ids:
        suggestions.append({
            "kind": "runtime",
            "title": "Recuperar Ollama local",
            "steps": [
                "Verifica que `ollama serve` esté levantado en `127.0.0.1:11434`.",
                "Comprueba que el modelo configurado exista con `ollama list`.",
                "Si sigue caído, mantén el guard en modo degradado y reintenta.",
            ],
        })
        user_guidance.append("Si el guard no responde con IA local, puedes seguir usando diagnóstico y acciones seguras mientras se recupera Ollama.")
        code_changes.append(KNOWN_FIXES["ollama_unreachable"])

    if "path_missing_static_root" in issue_ids:
        suggestions.append({
            "kind": "filesystem",
            "title": "Crear `static_root` faltante",
            "steps": [
                "Crea el directorio indicado por `STATIC_ROOT`.",
                "Repite el healthcheck para confirmar que el warning desaparece.",
            ],
        })
        code_changes.append(KNOWN_FIXES["path_missing_static_root"])

    recent_errors = execution_map.get("inspect_recent_errors") if isinstance(execution_map.get("inspect_recent_errors"), dict) else {}
    patterns = recent_errors.get("patterns") if isinstance(recent_errors.get("patterns"), list) else []
    pattern_names = {str(row.get("name") or "") for row in patterns if isinstance(row, dict)}
    runtime_cfg = execution_map.get("inspect_runtime_config") if isinstance(execution_map.get("inspect_runtime_config"), dict) else {}
    runtime_warnings = {str(x) for x in (runtime_cfg.get("warnings") or []) if str(x or "").strip()}

    if "DisallowedHost" in pattern_names or "testserver_no_esta_en_allowed_hosts" in runtime_warnings:
        suggestions.append({
            "kind": "config",
            "title": "Ajustar hosts permitidos",
            "steps": [
                "Añade el host real al env `ALLOWED_HOSTS` o al host público canónico.",
                "Si el origen también hace POST, revisa `CSRF_TRUSTED_ORIGINS`.",
            ],
        })
        code_changes.append({
            "title": "Blindar `ALLOWED_HOSTS` en local/test",
            "files": ["webstats/settings.py"],
            "reason": "Los logs muestran `DisallowedHost` y el runtime no incluye todos los hosts esperados.",
            "proposal": "Añadir normalización o defaults seguros para hosts de desarrollo/controlados sin abrir producción.",
        })
        user_guidance.append("Si ves un error de host inválido, abre la app con un dominio incluido en `ALLOWED_HOSTS` o ajusta la configuración del entorno.")

    if "HTTPS_on_HTTP_devserver" in pattern_names:
        suggestions.append({
            "kind": "runtime",
            "title": "Evitar HTTPS contra `runserver`",
            "steps": [
                "Usa `http://` al probar `runserver` local.",
                "Si necesitas HTTPS, colócalo detrás de un proxy que termine TLS.",
            ],
        })
        user_guidance.append("En local, `runserver` solo sirve HTTP. Si abres la URL con HTTPS, el sistema marcará error aunque la app esté bien.")

    route_result = execution_map.get("check_critical_routes") if isinstance(execution_map.get("check_critical_routes"), dict) else {}
    failing_routes = route_result.get("failing") if isinstance(route_result.get("failing"), list) else []
    if failing_routes:
        code_changes.append({
            "title": "Reparar rutas críticas no resueltas",
            "files": ["football/urls.py", "football/views.py"],
            "reason": f"Hay {len(failing_routes)} rutas críticas que no resuelven correctamente.",
            "proposal": "Revisar nombres `reverse`, imports y vistas enlazadas para restaurar las rutas críticas del producto.",
        })

    path_result = execution_map.get("inspect_critical_paths") if isinstance(execution_map.get("inspect_critical_paths"), dict) else {}
    missing_paths = [
        row for row in (path_result.get("paths") or [])
        if isinstance(row, dict) and not row.get("exists")
    ]
    if missing_paths:
        suggestions.append({
            "kind": "filesystem",
            "title": "Restaurar directorios críticos",
            "steps": [f"Crear o montar `{row.get('path')}`." for row in missing_paths[:4]],
        })

    if snapshot_diff and isinstance(snapshot_diff, dict):
        for item in (snapshot_diff.get("regressions") or [])[:3]:
            suggestions.append({
                "kind": "regression",
                "title": "Atajar regresión detectada",
                "steps": [str(item)],
            })
        repeated = snapshot_diff.get("repeated_issues") if isinstance(snapshot_diff.get("repeated_issues"), list) else []
        if repeated:
            user_guidance.append("Se repiten incidencias entre ejecuciones; conviene resolver la causa raíz antes de seguir operando.")

    for row in _known_fix_for_patterns(pattern_names, failing_routes):
        if row not in code_changes:
            code_changes.append(row)

    return {
        "suggestions": suggestions[:6],
        "code_changes": code_changes[:6],
        "patch_proposals": _build_patch_proposals(report, executions),
        "user_guidance": user_guidance[:6],
    }


def _fallback_response(report: dict, *, question: str, planner: dict, audience: str, autonomy_mode: str, degraded_reason: str = "", executions=None, snapshot_diff=None) -> dict:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    status = _base_status_from_issues(issues)
    highlights = []
    if summary.get("blockers"):
        highlights.append(f"Blockers: {summary.get('blockers')}")
    if summary.get("warnings"):
        highlights.append(f"Warnings: {summary.get('warnings')}")
    availability = (((report.get("evidence") or {}).get("local_llm") or {}).get("availability") or {})
    if availability.get("state") != "up":
        highlights.append(f"LLM local: {availability.get('state')}")
    if planner.get("requested_tools"):
        highlights.append("Acciones detectadas: " + ", ".join(planner.get("requested_tools")[:4]))
    if planner.get("tool_reasons"):
        highlights.extend([_truncate(row.get("reason"), 90) for row in planner.get("tool_reasons")[:2] if isinstance(row, dict)])
    for row in (executions or [])[:2]:
        if not isinstance(row, dict):
            continue
        tool = str(row.get("tool") or "")
        detail = row.get("result") if isinstance(row.get("result"), dict) else {}
        if tool == "inspect_repo_status" and isinstance(detail, dict) and detail.get("changed_count") is not None:
            highlights.append(f"Repo: {detail.get('changed_count')} cambio(s) detectado(s)")
        if tool == "git_commit" and isinstance(detail, dict) and detail.get("ok"):
            highlights.append("Commit creado correctamente")
        if tool == "git_push" and isinstance(detail, dict) and detail.get("ok"):
            highlights.append("Push realizado correctamente")
        if tool == "inspect_recent_errors" and isinstance(detail, dict):
            patterns = detail.get("patterns") if isinstance(detail.get("patterns"), list) else []
            if patterns:
                top = patterns[0]
                highlights.append(f"Log reciente: {top.get('name')} x{top.get('count')}")
        if tool == "check_critical_routes" and isinstance(detail, dict):
            failing = detail.get("failing") if isinstance(detail.get("failing"), list) else []
            if failing:
                highlights.append(f"Rutas con fallo: {len(failing)}")
    if audience == "guided":
        message = "He revisado el estado del sistema y te lo resumo en pasos simples."
    else:
        message = "He revisado el sistema con modo operativo y resumo el estado actual."
    if any(str((row or {}).get("tool") or "") == "git_push" and bool((row or {}).get("ok")) for row in (executions or [])):
        message = "He publicado los cambios solicitados y resumo el resultado."
    elif any(str((row or {}).get("tool") or "") == "git_commit" and bool((row or {}).get("ok")) for row in (executions or [])):
        message = "He creado el commit solicitado y resumo el resultado."
    if status == "fail":
        message += " Hay incidencias bloqueantes."
    elif status == "watch":
        message += " No veo blockers, pero sí incidencias a vigilar."
    else:
        message += " No veo incidencias críticas."
    if degraded_reason:
        message += f" Respuesta en modo degradado: {degraded_reason}."
    remediation = _build_remediation_plan(report, executions or [], snapshot_diff=snapshot_diff or {})
    actions = _fallback_actions(report, executions or [], planner)
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    runbook = planner.get("runbook") if isinstance(planner.get("runbook"), dict) else {}
    ui_actions = planner.get("followup_actions") if isinstance(planner.get("followup_actions"), list) else []
    return {
        "status": status if status in {"ok", "watch", "risk", "fail"} else "watch",
        "message": message,
        "highlights": highlights[:6],
        "actions": actions[:6],
        "plan": [
            *planner.get("steps", [])[:5],
            {"step": "Ejecutar herramientas seguras" if planner.get("requested_tools") else "Esperar nueva instrucción", "done": bool(executions)},
        ][:6],
        "executions": executions or [],
        "needs_confirmation": bool(planner.get("confirm_required")),
        "confirmation_text": str(planner.get("confirmation_text") or ""),
        "mode": autonomy_mode,
        "audience": audience,
        "degraded_reason": str(degraded_reason or ""),
        "task": task,
        "runbook": runbook,
        "silent_mode": bool(task.get("silent_mode")),
        "ui_actions": ui_actions[:4],
        "remediation": remediation,
        "snapshot_diff": snapshot_diff or {},
        "assistant_action": {},
        "improvement_proposals": [],
    }


def _normalize_llm_response(parsed, fallback: dict) -> dict:
    if not isinstance(parsed, dict):
        return fallback
    status = str(parsed.get("status") or fallback.get("status") or "watch").strip().lower()
    if status not in {"ok", "watch", "risk", "fail"}:
        status = fallback.get("status") or "watch"
    message = _truncate(parsed.get("message") or fallback.get("message") or "", 1800)
    highlights = [str(x) for x in (parsed.get("highlights") or []) if str(x or "").strip()][:6]
    actions = []
    for row in (parsed.get("actions") or [])[:6]:
        if isinstance(row, dict):
            actions.append({"label": _truncate(row.get("label"), 120), "reason": _truncate(row.get("reason"), 240)})
    merged = dict(fallback)
    merged.update({
        "status": status,
        "message": message,
        "highlights": highlights or fallback.get("highlights") or [],
        "actions": actions or fallback.get("actions") or [],
        "degraded_reason": str(fallback.get("degraded_reason") or ""),
        "task": fallback.get("task") or {},
        "runbook": fallback.get("runbook") or {},
        "silent_mode": bool(fallback.get("silent_mode")),
        "ui_actions": fallback.get("ui_actions") or [],
        "remediation": fallback.get("remediation") or {},
        "snapshot_diff": fallback.get("snapshot_diff") or {},
        "assistant_action": fallback.get("assistant_action") or {},
        "improvement_proposals": fallback.get("improvement_proposals") or [],
    })
    return merged


def run_system_guard_chat(
    *,
    question: str,
    history=None,
    run_smoke: bool = False,
    auto_fix: bool = False,
    maintenance_action: str = "",
    workspace=None,
    page_context=None,
    actor_id=None,
    autonomy_mode: str = "operator",
    audience: str = "technical",
    smoke_verbosity: int = 1,
    execute_confirmed: bool = False,
) -> dict:
    started_at = time.monotonic()
    autonomy_mode = autonomy_mode if autonomy_mode in AUTONOMY_MODES else "operator"
    audience = audience if audience in AUDIENCE_MODES else "technical"
    memory = _merge_memory(_load_memory(workspace), _load_memory_for_actor(workspace, actor_id=actor_id))
    planner = _plan_tools(
        question,
        run_smoke=run_smoke,
        auto_fix=auto_fix,
        maintenance_action=maintenance_action,
        autonomy_mode=autonomy_mode,
        page_context=page_context,
    )
    assistant_action = _resolve_assisted_action(question, workspace=workspace, page_context=page_context)
    maintenance_result = None
    executed_tools = []
    if planner.get("confirm_required") and execute_confirmed:
        planner["confirm_required"] = False
        planner["confirmation_text"] = ""
    if maintenance_action and not planner.get("confirm_required"):
        maintenance_result = _run_named_maintenance_action(maintenance_action)
        executed_tools.append(_serialize_execution(maintenance_action, maintenance_result))
    elif planner.get("requested_tools") and not planner.get("confirm_required"):
        executed_tools = _execute_tools(
            planner.get("requested_tools") or [],
            smoke_verbosity=smoke_verbosity,
            workspace=workspace,
            question=question,
        )
        run_smoke = bool(run_smoke or ("run_smoke" in (planner.get("requested_tools") or [])))
        auto_fix = bool(auto_fix or ("auto_fix" in (planner.get("requested_tools") or [])))
    report = run_system_guard(
        run_smoke=run_smoke,
        smoke_verbosity=smoke_verbosity,
        run_llm=False,
        auto_fix=auto_fix,
        page_context=page_context,
        memory=memory,
    )
    if maintenance_result is not None:
        report["maintenance_action"] = maintenance_result
    cfg = local_llm_config()
    previous_snapshot = _load_snapshots(workspace)[:1]
    previous_snapshot = previous_snapshot[0] if previous_snapshot else None
    fallback = _fallback_response(
        report,
        question=question,
        planner=planner,
        audience=audience,
        autonomy_mode=autonomy_mode,
        degraded_reason="",
        executions=executed_tools,
        snapshot_diff={},
    )
    current_snapshot = _snapshot_payload(report, fallback, executed_tools)
    snapshot_diff = _compare_snapshots(current_snapshot, previous_snapshot)
    fallback["snapshot_diff"] = snapshot_diff
    fallback["remediation"] = _build_remediation_plan(report, executed_tools or [], snapshot_diff=snapshot_diff)
    fallback["assistant_action"] = assistant_action if isinstance(assistant_action, dict) else {}
    fallback["improvement_proposals"] = _build_improvement_proposals(report, page_context=page_context, workspace=workspace)
    if assistant_action:
        action_message = str(assistant_action.get("message") or "").strip()
        if action_message:
            fallback["message"] = action_message
        if assistant_action.get("success"):
            fallback["status"] = "ok" if fallback.get("status") != "fail" else fallback.get("status")
        if assistant_action.get("needs_input"):
            fallback["status"] = "watch" if fallback.get("status") != "fail" else fallback.get("status")
        if assistant_action.get("permission_required"):
            fallback["status"] = "risk" if fallback.get("status") != "fail" else fallback.get("status")
        payload = assistant_action.get("payload") if isinstance(assistant_action.get("payload"), dict) else {}
        if payload:
            collected = []
            for key in ("name", "number", "position", "dominant_foot"):
                value = payload.get(key)
                if value not in ("", None):
                    collected.append(f"{key}:{value}")
            if collected:
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Datos capturados: {', '.join(collected[:4])}"]
        if assistant_action.get("missing_fields"):
            fallback["actions"] = [{
                "label": "Completar datos del jugador",
                "reason": "Faltan campos mínimos para ejecutar la petición.",
            }] + (fallback.get("actions") or [])
    parsed = None
    error = ""
    llm_used = bool(cfg.get("enabled") and str(cfg.get("provider") or "").lower() == "ollama")
    if llm_used and not planner.get("confirm_required"):
        parsed, error = call_ollama_json(
            build_system_guard_chat_prompt(report, question, _history_tail(history), planner=planner, memory=memory, audience=audience),
            model=cfg.get("model"),
            base_url=cfg.get("base_url"),
            timeout=min(max(_safe_int(cfg.get("timeout"), 8), 2), 20),
        )
    elif planner.get("confirm_required"):
        error = "execution_waiting_confirmation"
        fallback["degraded_reason"] = "esperando_confirmacion"
    else:
        error = "local_llm_disabled_or_unsupported"
        fallback["degraded_reason"] = error
    response = _normalize_llm_response(parsed, fallback if not error else dict(fallback, degraded_reason=fallback.get("degraded_reason") or error))
    latency_ms = int((time.monotonic() - started_at) * 1000)
    response["metrics"] = {
        "latency_ms": latency_ms,
        "llm_used": llm_used,
        "llm_available": isinstance(parsed, dict),
        "executed_tools": len(executed_tools),
    }
    response["memory_hint"] = _truncate(memory.get("summary"), 220)
    if snapshot_diff.get("regressions"):
        response["highlights"] = (response.get("highlights") or []) + [f"Regresión: {item}" for item in snapshot_diff.get("regressions", [])[:2]]
    elif snapshot_diff.get("improvements"):
        response["highlights"] = (response.get("highlights") or []) + [f"Mejora: {item}" for item in snapshot_diff.get("improvements", [])[:2]]
    _store_memory(workspace, report=report, response=response, executed_tools=executed_tools, question=question, page_context=page_context, actor_id=actor_id)
    _update_metrics(
        workspace,
        report=report,
        response=response,
        llm_used=llm_used,
        llm_ok=isinstance(parsed, dict),
        executed_tools=executed_tools,
        latency_ms=latency_ms,
    )
    audit_event = {
        "created_at": _now_iso(),
        "actor_id": int(actor_id or 0),
        "question": _truncate(question, 220),
        "status": str(response.get("status") or "").strip()[:32],
        "task_kind": str((response.get("task") or {}).get("kind") or (planner.get("task") or {}).get("kind") or "").strip()[:32],
        "runbook": str((response.get("runbook") or {}).get("key") or (planner.get("runbook") or {}).get("key") or "").strip()[:64],
        "confirmed": bool(execute_confirmed),
        "executed_tools": [str(row.get("tool") or "") for row in executed_tools if isinstance(row, dict)][:8],
        "silent_mode": bool(response.get("silent_mode")),
    }
    _append_audit_log(workspace, audit_event)
    _store_snapshot(workspace, report=report, response=response, executions=executed_tools)
    queue_rows = _load_task_queue(workspace)
    return {
        "ok": bool(report.get("ok")),
        "report": report,
        "planner": planner,
        "audit": audit_event,
        "task_queue": {
            "counts": _task_state_counts(queue_rows),
            "items": queue_rows[:6],
        },
        "chat": {
            "available": isinstance(parsed, dict),
            "degraded": not isinstance(parsed, dict),
            "error": str(error or ""),
            "response": response,
            "quick_actions": [{"key": key, "label": meta.get("label")} for key, meta in CHAT_ACTIONS.items()],
            "tool_catalog": _tool_catalog(),
            "autonomy_modes": sorted(AUTONOMY_MODES),
            "audiences": sorted(AUDIENCE_MODES),
            "memory": _merge_memory(_load_memory(workspace), _load_memory_for_actor(workspace, actor_id=actor_id)),
        },
    }
