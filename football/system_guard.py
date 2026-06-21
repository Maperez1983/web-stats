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

from football.healthchecks import run_system_healthcheck
from football.library_repositories import (
    LIBRARY_REPOSITORY_AI_TRAINER,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    normalize_library_repository,
)
from football.local_llm import call_ollama_json, local_llm_config
from football.models import Match, Player, SessionTask, TrainingMicrocycle, TrainingSession, WorkspaceCompetitionContext, WorkspacePreference, WorkspaceSeason, WorkspaceTeam
from football.session_import_services import get_or_create_inbox_microcycle, get_or_create_library_session_with_repository
from football.session_plan_fields import serialize_session_plan_fields
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

CODE_INTERVENTION_CATALOG = {
    "dev_testserver_allowed_host": {
        "title": "Añadir `testserver` a ALLOWED_HOSTS de desarrollo",
        "summary": "Evita DisallowedHost en validaciones y flujos locales controlados cuando Django usa `testserver`.",
        "match_terms": ["disallowedhost", "testserver", "allowed hosts", "allowed_hosts", "host header"],
        "auto_apply": True,
        "files": ["webstats/settings.py"],
        "patches": [{
            "path": "webstats/settings.py",
            "search": "for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')",
            "replace": "for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')",
        }],
    },
    "widget_library_ai_navigation_keywords": {
        "title": "Afinar navegación del widget hacia biblioteca IA Trainer",
        "summary": "Refuerza las keywords del widget para que órdenes como `abre biblioteca ia trainer` resuelvan antes a biblioteca que a la portada de IA Trainer.",
        "match_terms": ["biblioteca ia trainer", "biblioteca ai trainer", "widget ollana biblioteca", "navegacion widget biblioteca", "widget lleve al usuario a biblioteca", "widget biblioteca de tareas"],
        "auto_apply": True,
        "files": ["football/templates/football/includes/global_guard_widget.html"],
        "patches": [
            {
                "path": "football/templates/football/includes/global_guard_widget.html",
                "search": "    { key: 'library', label: 'Biblioteca de tareas', url: \"{% url 'sessions' %}?tab=library&library_repo=traditional{% if active_team %}&team={{ active_team.id }}{% endif %}{% if active_workspace %}&workspace={{ active_workspace.id }}{% endif %}\", keywords: ['biblioteca de tareas', 'biblioteca', 'tareas', 'ejercicios', 'task library'] },",
                "replace": "    { key: 'library', label: 'Biblioteca de tareas', url: \"{% url 'sessions' %}?tab=library&library_repo=traditional{% if active_team %}&team={{ active_team.id }}{% endif %}{% if active_workspace %}&workspace={{ active_workspace.id }}{% endif %}\", keywords: ['biblioteca de tareas', 'biblioteca', 'tareas', 'ejercicios', 'task library'] },\n    { key: 'library_ai_trainer', label: 'Biblioteca IA Trainer', url: \"{% url 'sessions' %}?tab=library&library_repo=ai_trainer&library_source=created{% if active_team %}&team={{ active_team.id }}{% endif %}{% if active_workspace %}&workspace={{ active_workspace.id }}{% endif %}\", keywords: ['biblioteca ia trainer', 'biblioteca ai trainer', 'tareas ia trainer', 'biblioteca trainer'] },",
            },
            {
                "path": "football/templates/football/includes/global_guard_widget.html",
                "search": "      if (route.key === 'library' && text.includes('biblioteca')) score += 2;",
                "replace": "      if (route.key === 'library' && text.includes('biblioteca')) score += 2;\n      if (route.key === 'library_ai_trainer' && text.includes('biblioteca') && (text.includes('trainer') || text.includes('ia'))) score += 6;",
            },
        ],
    },
    "widget_visibility_and_mount": {
        "title": "Verificar visibilidad y montaje global del widget Ollana",
        "summary": "Restaurar el include del widget en IA Trainer y revisar que el shell se monte en `body`, conserve `z-index` alto y no quede oculto por layouts o shell PWA.",
        "match_terms": ["widget ollana no aparece", "widget no se ve", "chat abajo derecha", "montaje widget", "visibilidad ollana"],
        "auto_apply": True,
        "files": [
            "football/templates/football/ai_trainer.html",
            "football/templates/football/includes/global_guard_widget.html",
            "football/templates/football/pwa_head.html",
            "football/templates/football/includes/dragon_nav.html",
        ],
        "patches": [{
            "path": "football/templates/football/ai_trainer.html",
            "search": "  <body>\n    {% include 'football/includes/dragon_nav.html' with hide_global_guard_widget=True %}\n    <main class=\"page\">",
            "replace": "  <body>\n    {% include 'football/includes/dragon_nav.html' with hide_global_guard_widget=True %}\n    {% include 'football/includes/global_guard_widget.html' %}\n    <main class=\"page\">",
        }],
    },
    "pitch3d_trigger_and_modal_flow": {
        "title": "Revisar disparadores y modal de pitch 3D",
        "summary": "Inspeccionar si hay múltiples triggers, bindings parciales o modal 3D montado fuera de secuencia en task builder.",
        "match_terms": ["pitch 3d", "pitch3d", "estadio 3d", "modal 3d", "representacion 3d", "representación 3d"],
        "auto_apply": True,
        "files": [
            "football/templates/football/task_builder.html",
            "football/static/football/js/sessions_tactical_pad.js",
            "football/views.py",
        ],
        "patches": [
            {
                "path": "football/templates/football/task_builder.html",
                "search": '<button type="button" class="surface-trigger" id="pitch-3d-open" title="Representación 3D (presentación)" aria-label="Representación 3D">',
                "replace": '<button type="button" class="surface-trigger" id="pitch-3d-open-standard" data-pitch3d-trigger="1" title="Representación 3D (presentación)" aria-label="Representación 3D">',
            },
            {
                "path": "football/templates/football/task_builder.html",
                "search": '{% if tactics_mode %}\n                  <button type="button" class="surface-trigger" id="pitch-3d-open" title="Representación 3D (presentación)" aria-label="Representación 3D">',
                "replace": '{% if tactics_mode %}\n                  <button type="button" class="surface-trigger" id="pitch-3d-open-tactics" data-pitch3d-trigger="1" title="Representación 3D (presentación)" aria-label="Representación 3D">',
            },
            {
                "path": "football/static/football/js/sessions_tactical_pad.js",
                "search": "if (document.getElementById('pitch-3d-open')) return;",
                "replace": "if (document.querySelector('[data-pitch3d-trigger=\"1\"]')) return;",
            },
            {
                "path": "football/static/football/js/sessions_tactical_pad.js",
                "search": "btn.id = 'pitch-3d-open';",
                "replace": "btn.id = 'pitch-3d-open-tactics';\n\t\t\t            btn.dataset.pitch3dTrigger = '1';",
            },
            {
                "path": "football/static/football/js/sessions_tactical_pad.js",
                "search": "const pitch3dOpenBtn = document.getElementById('pitch-3d-open');",
                "replace": "const pitch3dOpenBtn = document.querySelector('[data-pitch3d-trigger=\"1\"]');",
            },
            {
                "path": "football/static/football/js/sessions_tactical_pad.js",
                "search": "const trigger = ev.target?.closest?.('#pitch-3d-open');",
                "replace": "const trigger = ev.target?.closest?.('[data-pitch3d-trigger=\"1\"]');",
            },
        ],
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
SCHEDULED_GUARD_STATE_PREF_KEY = "system_guard:scheduled_cycle:v1"
INCIDENT_LEDGER_PREF_KEY = "system_guard:incident_ledger:v1"
OPERATOR_PROFILE_PREF_KEY = "system_guard:operator_profile:v1"
SCHEDULED_GUARD_INTERVAL_SECONDS = 300
ACTION_PERMISSION_MATRIX = {
    "inspect_system": {"requires_manage_guard": False, "requires_code_operator": False, "scope": "system"},
    "guide_user": {"requires_manage_guard": False, "requires_code_operator": False, "scope": "user"},
    "navigate_modules": {"requires_manage_guard": False, "requires_code_operator": False, "scope": "user"},
    "create_player": {"requires_manage_guard": True, "requires_code_operator": False, "scope": "business"},
    "create_session": {"requires_manage_guard": True, "requires_code_operator": False, "scope": "business"},
    "create_task": {"requires_manage_guard": True, "requires_code_operator": False, "scope": "business"},
    "repair_code": {"requires_manage_guard": True, "requires_code_operator": True, "scope": "code"},
    "publish_changes": {"requires_manage_guard": True, "requires_code_operator": True, "scope": "code"},
    "inspect_repo": {"requires_manage_guard": True, "requires_code_operator": True, "scope": "code"},
    "validate_changes": {"requires_manage_guard": True, "requires_code_operator": True, "scope": "code"},
    "monitor_incidents": {"requires_manage_guard": True, "requires_code_operator": False, "scope": "system"},
}
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
    "code_diagnostics": {
        "label": "Diagnóstico técnico de código",
        "goal": "Entender el estado del repositorio y la validación antes de tocar código.",
        "steps": [
            "Inspeccionar repo y cambios activos.",
            "Ejecutar validación técnica mínima.",
            "Definir siguiente paso seguro sobre código.",
        ],
    },
    "code_execution": {
        "label": "Operación técnica gobernada",
        "goal": "Preparar una intervención de código con validación y publicación trazables.",
        "steps": [
            "Inspeccionar repo y riesgo técnico.",
            "Validar cambios y resultado esperado.",
            "Aplicar o publicar solo con permisos y confirmación.",
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
PROACTIVE_IMPROVEMENT_CATALOG = {
    "stability_hardening": {
        "severity": "info",
        "runbook": "silent_diagnostics",
        "task_kind": "improve",
        "summary": "El sistema está estable; conviene convertir este estado en prevención y cobertura.",
        "tools": ["inspect_guard_history", "inspect_repo_status"],
    },
    "operator_memory_refresh": {
        "severity": "info",
        "runbook": "user_guidance",
        "task_kind": "improve",
        "summary": "Hay patrones repetidos del usuario y conviene reforzar accesos rápidos y memoria operativa.",
        "tools": ["inspect_guard_history"],
    },
}
OLLANA_CAPABILITY_VERSION = "v2"
OLLANA_SYSTEM_OS_VERSION = "v1"
OLLANA_CAPABILITIES = {
    "identity": {
        "name": "Ollana",
        "role": "system_copilot",
        "version": OLLANA_CAPABILITY_VERSION,
    },
    "modes": {
        "silent_operator": True,
        "guided_assistant": True,
        "functional_executor": True,
        "code_operator": True,
        "continuous_operator": True,
    },
    "skills": [
        {"key": "inspect_system", "label": "Inspección del sistema", "scope": "system", "requires_code_operator": False},
        {"key": "guide_user", "label": "Guía de usuario", "scope": "user", "requires_code_operator": False},
        {"key": "navigate_modules", "label": "Navegación por módulos", "scope": "user", "requires_code_operator": False},
        {"key": "create_player", "label": "Alta de jugador", "scope": "business", "requires_code_operator": False},
        {"key": "create_session", "label": "Crear sesión", "scope": "business", "requires_code_operator": False},
        {"key": "create_task", "label": "Crear tarea", "scope": "business", "requires_code_operator": False},
        {"key": "monitor_incidents", "label": "Memoria de incidencias", "scope": "system", "requires_code_operator": False},
        {"key": "inspect_repo", "label": "Inspección de repositorio", "scope": "code", "requires_code_operator": True},
        {"key": "validate_changes", "label": "Validación técnica", "scope": "code", "requires_code_operator": True},
        {"key": "repair_code", "label": "Reparación técnica", "scope": "code", "requires_code_operator": True},
        {"key": "publish_changes", "label": "Commit y push", "scope": "code", "requires_code_operator": True},
    ],
}
OLLANA_ACTION_SURFACES = {
    "conversation": ["guide_user", "navigate_modules"],
    "business": ["create_player", "create_session", "create_task"],
    "system": ["inspect_system", "monitor_incidents"],
    "code": ["inspect_repo", "validate_changes", "repair_code", "publish_changes"],
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


def _route_filters_for_question(question: str, route_key: str) -> dict:
    text = str(question or "").strip().lower()
    filters = {}
    if route_key == "library":
        if any(token in text for token in ["ia-trainer", "ia trainer", "ai trainer", "biblioteca ia"]):
            filters["library_repo"] = LIBRARY_REPOSITORY_AI_TRAINER
        elif any(token in text for token in ["interactiva", "interactive", "interactiva"]):
            filters["library_repo"] = LIBRARY_REPOSITORY_INTERACTIVE
        elif any(token in text for token in ["pdf", "tradicional", "clásica", "clasica"]):
            filters["library_repo"] = LIBRARY_REPOSITORY_TRADITIONAL
        if any(token in text for token in ["creadas", "creados", "nuevas", "nuevos"]):
            filters["library_source"] = "created"
    if route_key == "sessions":
        if "microciclo" in text or "microciclos" in text:
            filters["tab"] = "microcycles"
        elif "editor" in text:
            filters["sessions_view"] = "editor"
    if route_key == "players":
        if "stats" in text or "estad" in text:
            filters["tab"] = "stats"
    return filters


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
        if str(route.get("key") or "") == "library" and any(token in text for token in ["biblioteca", "tareas", "ejercicios", "task library"]):
            score += 5
        if score > 0 and (best is None or score > best.get("score", 0)):
            route_copy = dict(route)
            extra_filters = _route_filters_for_question(question, str(route.get("key") or ""))
            if extra_filters:
                base_url = str(route_copy.get("url") or "").split("?", 1)[0]
                current_query = {}
                raw_url = str(route_copy.get("url") or "")
                if "?" in raw_url:
                    for chunk in raw_url.split("?", 1)[1].split("&"):
                        if "=" not in chunk:
                            continue
                        left, right = chunk.split("=", 1)
                        current_query[left] = right
                current_query.update({str(key): value for key, value in extra_filters.items() if value not in (None, "", 0, "0")})
                route_copy["url"] = f"{base_url}{_compact_query(current_query)}"
                route_copy["filters"] = extra_filters
            best = {"score": score, **route_copy}
    return best if best and best.get("score", 0) > 0 else None


def _build_task_profile(question: str, *, intent: str, maintenance_action: str = "", page_context=None) -> dict:
    route_target = _match_route_target(question, page_context)
    kind = "support"
    scope = "user"
    silent_mode = True
    runbook_key = "silent_diagnostics"
    lower_question = str(question or "").lower()
    code_markers = [
        "codigo", "código", "repo", "repositorio", "git", "commit", "push", "tests", "check",
        "3d", "pitch3d", "estadio", "stadium", "render", "visualiza", "visualiza", "canvas", "glb",
    ]
    code_related = any(token in lower_question for token in code_markers)
    if route_target and re.search(r"\b(abre|abrir|ll[ée]vame|llevame|ve a|ir a|quiero ir|quiero abrir|quiero ver)\b", str(question or "").lower()):
        kind = "navigate"
        scope = "user"
        silent_mode = False
        runbook_key = "user_navigation"
    elif intent in {"create_player", "create_session", "create_task"}:
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
    elif intent == "feature_request":
        kind = "build"
        scope = "code"
        silent_mode = True
        runbook_key = "code_execution"
    elif intent in {"repair"} or maintenance_action in {"regenerate_task_previews", "ai_trainer_reindex"}:
        kind = "repair" if intent == "repair" else "maintenance"
        scope = "code" if (kind == "repair" and code_related) else ("system" if kind == "repair" else "maintenance")
        silent_mode = True
        runbook_key = "code_execution" if (kind == "repair" and code_related) else ("safe_repair" if kind == "repair" else "maintenance_runbook")
    elif intent in {"inspect_repo", "operator_validate"} or code_related:
        kind = "code_workflow"
        scope = "code"
        silent_mode = True
        runbook_key = "code_diagnostics"
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
        "target_summary": _truncate(question, 220),
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


def _contextual_flow_actions(page_context=None) -> list[dict]:
    context = page_context if isinstance(page_context, dict) else {}
    page = str(context.get("page") or "").strip().lower()
    tab = str(context.get("tab") or "").strip().lower()
    session_id = _safe_int(context.get("session_id") or context.get("selected_session_id"), 0)
    task_id = _safe_int(context.get("task_id") or context.get("source_task_id"), 0)
    match_id = _safe_int(context.get("match_id"), 0)
    microcycle_id = _safe_int(context.get("microcycle_id") or context.get("prefill_microcycle_id"), 0)
    actions = []
    if page == "sessions":
        if session_id:
            actions.append({
                "type": "prompt",
                "label": "Optimizar sesión actual",
                "prompt": "Analiza la sesión abierta y dime el siguiente ajuste útil de carga, foco o tareas.",
                "reason": "Trabajar sobre la sesión que ya está abierta.",
            })
        if task_id:
            actions.append({
                "type": "prompt",
                "label": "Revisar tarea actual",
                "prompt": "Revisa la tarea abierta y propón una mejora táctica, metodológica o visual.",
                "reason": "Profundizar sobre la tarea en foco.",
            })
        if microcycle_id:
            actions.append({
                "type": "prompt",
                "label": "Revisar microciclo",
                "prompt": "Resume el microciclo abierto y dime la siguiente decisión útil.",
                "reason": "Ayuda contextual sobre el microciclo activo.",
            })
        if tab == "library":
            actions.append({
                "type": "prompt",
                "label": "Curar biblioteca",
                "prompt": "Analiza la biblioteca actual y dime qué tarea falta o qué contenido conviene mejorar.",
                "reason": "Aprovechar el contexto de biblioteca abierta.",
            })
    if page == "coach-roster":
        actions.append({
            "type": "prompt",
            "label": "Revisar plantilla",
            "prompt": "Analiza la plantilla actual y dime qué información falta o qué acción operativa conviene hacer ahora.",
            "reason": "Contexto natural de gestión de plantilla.",
        })
    if page in {"match-hub", "match-action-page"} or match_id:
        actions.append({
            "type": "prompt",
            "label": "Analizar partido activo",
            "prompt": "Explica el partido activo, el rival y la siguiente decisión útil para el staff.",
            "reason": "Contexto directo del flujo de partido.",
        })
    if page == "ai-trainer":
        actions.append({
            "type": "prompt",
            "label": "Trabajar en IA Trainer",
            "prompt": "Dime qué flujo de IA Trainer está más alineado con esta pantalla y qué debería hacer ahora.",
            "reason": "Ayuda nativa sobre el módulo IA Trainer.",
        })
    seen = set()
    deduped = []
    for row in actions:
        label = str((row or {}).get("label") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        deduped.append(row)
    return deduped[:4]


def _followup_actions(task: dict, planner: dict, *, page_context=None) -> list[dict]:
    actions = list(_contextual_flow_actions(page_context))
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
        sessions_route = next((row for row in _guard_route_catalog(page_context) if row.get("key") == "sessions"), None)
        if sessions_route and sessions_route.get("url"):
            actions.append({
                "type": "navigate",
                "label": "Abrir entrenamiento",
                "url": str(sessions_route.get("url") or ""),
                "reason": "Acceso directo a sesiones y microciclos.",
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
    if str(task.get("scope") or "") == "code":
        actions.append({
            "type": "prompt",
            "label": "Inspeccionar repo",
            "prompt": "Revisa el repositorio, el diff y el riesgo técnico antes de tocar código.",
            "reason": "Iniciar diagnóstico técnico sobre código.",
        })
        actions.append({
            "type": "prompt",
            "label": "Validar cambios",
            "prompt": "Ejecuta validación técnica y dime si el cambio está listo para publicarse.",
            "reason": "Forzar un paso de validación antes de publicar.",
        })
    if task.get("kind") == "build":
        actions.append({
            "type": "prompt",
            "label": "Diseñar cambio",
            "prompt": "Desglosa la funcionalidad en archivos, impacto y validación mínima.",
            "reason": "Convertir la petición abierta en un cambio implementable.",
        })
    seen = set()
    deduped = []
    for row in actions:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        deduped.append(row)
    return deduped[:6]


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


def _json_safe_payload(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        if isinstance(value, dict):
            return {str(key): _json_safe_payload(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe_payload(item) for item in value]
        return str(value)


def _catalog_candidates_for_question(question: str) -> list[dict]:
    text = str(question or "").strip().lower()
    if not text:
        return []
    rows = []
    for key, item in CODE_INTERVENTION_CATALOG.items():
        if not isinstance(item, dict):
            continue
        terms = [str(term or "").strip().lower() for term in (item.get("match_terms") or []) if str(term or "").strip()]
        if not terms:
            continue
        score = sum(1 for term in terms if term in text)
        if score <= 0:
            continue
        rows.append({
            "key": str(key),
            "score": score,
            "title": str(item.get("title") or key),
            "summary": str(item.get("summary") or ""),
            "auto_apply": bool(item.get("auto_apply")),
            "files": [str(path or "") for path in (item.get("files") or []) if str(path or "").strip()][:6],
        })
    rows.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("key") or "")))
    return rows[:3]


def _resolve_catalog_repo_path(relative_path: str) -> Path | None:
    rel = str(relative_path or "").strip()
    if not rel:
        return None
    base_dir = Path(app_settings.BASE_DIR).resolve()
    target = (base_dir / rel).resolve()
    try:
        target.relative_to(base_dir)
    except Exception:
        return None
    return target


def _apply_exact_text_patch(relative_path: str, search: str, replace: str) -> dict:
    target = _resolve_catalog_repo_path(relative_path)
    if target is None:
        return {"ok": False, "error": "invalid_patch_path", "path": str(relative_path or "")}
    if not target.exists():
        return {"ok": False, "error": "patch_target_missing", "path": str(target)}
    try:
        original = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": f"read_failed:{exc.__class__.__name__}", "path": str(target)}
    if str(search or "") not in original:
        return {"ok": False, "error": "search_not_found", "path": str(target), "applied": False}
    updated = original.replace(str(search), str(replace), 1)
    if updated == original:
        return {"ok": True, "path": str(target), "applied": False, "detail": "already_up_to_date"}
    try:
        target.write_text(updated, encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": f"write_failed:{exc.__class__.__name__}", "path": str(target)}
    return {"ok": True, "path": str(target), "applied": True}


def _execute_catalog_code_intervention(candidate_key: str) -> dict:
    item = CODE_INTERVENTION_CATALOG.get(str(candidate_key or "").strip()) or {}
    patches = [row for row in (item.get("patches") or []) if isinstance(row, dict)]
    if not patches:
        return {"ok": False, "error": "no_patches_defined", "candidate_key": str(candidate_key or "")}
    results = []
    applied = 0
    for patch in patches:
        result = _apply_exact_text_patch(
            str(patch.get("path") or ""),
            str(patch.get("search") or ""),
            str(patch.get("replace") or ""),
        )
        results.append(result)
        if result.get("applied"):
            applied += 1
        elif not result.get("ok") and result.get("error") != "search_not_found":
            return {
                "ok": False,
                "candidate_key": str(candidate_key or ""),
                "title": str(item.get("title") or candidate_key),
                "results": results,
                "error": str(result.get("error") or "catalog_patch_failed"),
            }
    return {
        "ok": bool(applied > 0),
        "candidate_key": str(candidate_key or ""),
        "title": str(item.get("title") or candidate_key),
        "results": results,
        "applied_count": applied,
        "noop": applied == 0,
    }


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
    incident_ledger = _load_incident_ledger(workspace) if workspace else []
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
        "recent_fixes": [str(item) for item in (memory.get("recent_fixes") or [])[:4]],
        "recent_runbooks": [str(item) for item in (memory.get("recent_runbooks") or [])[:4]],
        "audit_count": len(audit_rows),
        "recent_audits": audit_rows[:3],
        "incident_ledger_count": len(incident_ledger),
        "incident_ledger_preview": incident_ledger[:3],
        "task_queue": _task_state_counts(_load_task_queue(workspace)) if workspace else {"pending": 0, "running": 0, "completed": 0, "blocked": 0},
        "task_queue_preview": _load_task_queue(workspace)[:3] if workspace else [],
        "proactive_state": _load_proactive_state(workspace) if workspace else {},
        "scheduled_state": _scheduled_guard_state(workspace) if workspace else {},
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


def _detect_proactive_improvements(report: dict, *, workspace=None, actor_id=None) -> list[dict]:
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    queue_counts = _task_state_counts(_load_task_queue(workspace)) if workspace else {"pending": 0, "running": 0, "completed": 0, "blocked": 0}
    profile = _load_operator_profile(workspace, actor_id=actor_id) if workspace else {}
    improvements = []
    if _safe_int(summary.get("blockers"), 0) == 0 and _safe_int(summary.get("warnings"), 0) == 0 and queue_counts.get("pending", 0) == 0:
        meta = PROACTIVE_IMPROVEMENT_CATALOG["stability_hardening"]
        improvements.append({
            "detector": "stability_hardening",
            "severity": meta["severity"],
            "runbook": meta["runbook"],
            "task_kind": meta["task_kind"],
            "title": "Consolidar estabilidad actual",
            "summary": meta["summary"],
            "tools": meta["tools"],
            "auto_execute": False,
        })
    recurring = [row for row in (profile.get("recurring_intents") or []) if isinstance(row, dict)]
    top_intent = next((row for row in recurring if _safe_int(row.get("count"), 0) >= 2), None)
    if profile.get("preferred_route_key") and top_intent:
        meta = PROACTIVE_IMPROVEMENT_CATALOG["operator_memory_refresh"]
        improvements.append({
            "detector": "operator_memory_refresh",
            "severity": meta["severity"],
            "runbook": meta["runbook"],
            "task_kind": meta["task_kind"],
            "title": f"Optimizar flujo frecuente: {top_intent.get('intent')}",
            "summary": meta["summary"],
            "tools": meta["tools"],
            "auto_execute": False,
        })
    return improvements[:4]


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
    improvements = _detect_proactive_improvements(report, workspace=workspace, actor_id=actor_id)
    created = []
    executed = []
    for detection in detections + improvements:
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
        "last_improvement_count": len(improvements),
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
        "improvements": improvements,
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


def _record_task_queue_event(
    workspace,
    *,
    title: str,
    summary: str,
    task_kind: str,
    runbook: str,
    tools: list[str] | None = None,
    source: str = "manual",
    status: str = "completed",
    question: str = "",
    result_summary: str = "",
    executions: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    if not workspace:
        return {}
    task = _new_task_entry(
        detector="manual_request",
        title=title,
        summary=summary,
        severity="info",
        runbook=runbook,
        task_kind=task_kind,
        tools=list(tools or []),
        source=source,
        question=question,
        auto_execute=False,
    )
    if isinstance(metadata, dict) and metadata:
        task["metadata"] = _json_safe_payload(metadata)
    saved = _enqueue_task(workspace, task)
    return _update_task_entry(
        workspace,
        str(saved.get("id") or ""),
        status=status,
        executions=list(executions or []),
        result_summary=result_summary,
        metadata=_json_safe_payload(metadata) if isinstance(metadata, dict) and metadata else saved.get("metadata", {}),
        finished_at=_now_iso() if status in {"completed", "blocked"} else "",
    ) or saved


def _scheduled_guard_state(workspace) -> dict:
    payload = _pref_value(workspace, SCHEDULED_GUARD_STATE_PREF_KEY, {})
    return payload if isinstance(payload, dict) else {}


def _store_scheduled_guard_state(workspace, payload: dict):
    if not workspace:
        return
    _store_pref_value(workspace, SCHEDULED_GUARD_STATE_PREF_KEY, payload if isinstance(payload, dict) else {})


def _maybe_run_scheduled_guard_cycle(*, workspace, actor_id=None, page_context=None, force: bool = False) -> dict:
    if not workspace:
        return {"ran": False, "reason": "workspace_required"}
    state = _scheduled_guard_state(workspace)
    now_ts = int(time.time())
    last_started = _safe_int(state.get("last_started_ts"), 0)
    if not force and last_started and (now_ts - last_started) < int(SCHEDULED_GUARD_INTERVAL_SECONDS):
        return {"ran": False, "reason": "interval_not_elapsed", "state": state}
    next_state = {
        "last_started_ts": now_ts,
        "last_started_at": _now_iso(),
    }
    _store_scheduled_guard_state(workspace, next_state)
    result = run_proactive_guard_cycle(
        workspace=workspace,
        actor_id=actor_id,
        allow_safe_repairs=True,
        page_context=page_context or {"page": "scheduled-guard-cycle"},
    )
    next_state.update({
        "last_finished_ts": int(time.time()),
        "last_finished_at": _now_iso(),
        "last_queue_counts": result.get("queue_counts") or {},
        "last_detection_count": len(result.get("detections") or []),
    })
    _store_scheduled_guard_state(workspace, next_state)
    return {"ran": True, "result": result, "state": next_state}


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


def _permission_profile(page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    can_manage = bool(context.get("can_manage_guard"))
    can_code = bool(context.get("can_operate_guard_code"))
    policies = []
    for action_key, policy in ACTION_PERMISSION_MATRIX.items():
        requires_manage = bool(policy.get("requires_manage_guard"))
        requires_code = bool(policy.get("requires_code_operator"))
        allowed = (not requires_manage or can_manage) and (not requires_code or can_code)
        policies.append({
            "action": str(action_key),
            "scope": str(policy.get("scope") or ""),
            "requires_manage_guard": requires_manage,
            "requires_code_operator": requires_code,
            "allowed": bool(allowed),
        })
    return {
        "roles": {
            "can_manage_guard": can_manage,
            "can_operate_guard_code": can_code,
        },
        "policies": policies,
    }


def _authorize_guard_action(action_key: str, *, page_context=None) -> dict:
    policy = ACTION_PERMISSION_MATRIX.get(str(action_key or "").strip()) or {}
    profile = _permission_profile(page_context=page_context)
    roles = profile.get("roles") if isinstance(profile.get("roles"), dict) else {}
    requires_manage = bool(policy.get("requires_manage_guard"))
    requires_code = bool(policy.get("requires_code_operator"))
    allowed = (not requires_manage or bool(roles.get("can_manage_guard"))) and (not requires_code or bool(roles.get("can_operate_guard_code")))
    reasons = []
    if requires_manage and not bool(roles.get("can_manage_guard")):
        reasons.append("requires_manage_guard")
    if requires_code and not bool(roles.get("can_operate_guard_code")):
        reasons.append("requires_code_operator")
    return {
        "allowed": bool(allowed),
        "reasons": reasons,
        "policy": {
            "action": str(action_key or ""),
            "requires_manage_guard": requires_manage,
            "requires_code_operator": requires_code,
            "scope": str(policy.get("scope") or ""),
        },
    }


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
        "recent_fixes": [str(x) for x in (payload.get("recent_fixes") or []) if str(x or "").strip()][:12],
        "recent_runbooks": [str(x) for x in (payload.get("recent_runbooks") or []) if str(x or "").strip()][:12],
        "recent_questions": [str(x) for x in (payload.get("recent_questions") or []) if str(x or "").strip()][:10],
        "recent_pages": [str(x) for x in (payload.get("recent_pages") or []) if str(x or "").strip()][:8],
        "last_status": str(payload.get("last_status") or "").strip()[:32],
        "last_error": str(payload.get("last_error") or "").strip()[:200],
        "turn_count": _safe_int(payload.get("turn_count"), 0),
        "last_updated": str(payload.get("last_updated") or "").strip()[:64],
    }


def _operator_profile_pref_key(actor_id=None) -> str:
    if actor_id:
        return f"{OPERATOR_PROFILE_PREF_KEY}:user:{int(actor_id)}"
    return OPERATOR_PROFILE_PREF_KEY


def _normalize_operator_profile(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    recurring = []
    for row in (payload.get("recurring_intents") or [])[:6]:
        if not isinstance(row, dict):
            continue
        recurring.append({
            "intent": str(row.get("intent") or "").strip()[:64],
            "count": _safe_int(row.get("count"), 0),
        })
    return {
        "preferred_route_key": str(payload.get("preferred_route_key") or "").strip()[:64],
        "preferred_route_label": str(payload.get("preferred_route_label") or "").strip()[:120],
        "last_requested_module": str(payload.get("last_requested_module") or "").strip()[:120],
        "recent_destinations": [str(x) for x in (payload.get("recent_destinations") or []) if str(x or "").strip()][:8],
        "successful_actions": [str(x) for x in (payload.get("successful_actions") or []) if str(x or "").strip()][:8],
        "code_focus_areas": [str(x) for x in (payload.get("code_focus_areas") or []) if str(x or "").strip()][:8],
        "recurring_intents": recurring,
        "last_updated": str(payload.get("last_updated") or "").strip()[:64],
    }


def _load_operator_profile(workspace, actor_id=None) -> dict:
    payload = _pref_value(workspace, _operator_profile_pref_key(actor_id), {})
    return _normalize_operator_profile(payload)


def _bump_intent_counter(rows: list[dict], intent: str) -> list[dict]:
    intent_key = str(intent or "").strip()
    counters = []
    found = False
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        current_intent = str(row.get("intent") or "").strip()
        count = _safe_int(row.get("count"), 0)
        if intent_key and current_intent == intent_key:
            count += 1
            found = True
        counters.append({"intent": current_intent[:64], "count": count})
    if intent_key and not found:
        counters.append({"intent": intent_key[:64], "count": 1})
    counters.sort(key=lambda row: (-_safe_int(row.get("count"), 0), str(row.get("intent") or "")))
    return counters[:6]


def _store_operator_profile(workspace, *, actor_id=None, planner=None, assistant_action=None, question: str = "", page_context=None):
    if not workspace:
        return
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    current = _load_operator_profile(workspace, actor_id=actor_id)
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    route_target = task.get("route_target") if isinstance(task.get("route_target"), dict) else {}
    candidate_route = route_target if route_target.get("key") else {}
    if isinstance(assistant_action.get("navigate_to"), dict) and assistant_action.get("navigate_to", {}).get("key"):
        candidate_route = assistant_action.get("navigate_to")
    successful = []
    if assistant_action.get("success") and str(assistant_action.get("kind") or "").strip():
        successful.append(str(assistant_action.get("kind") or "").strip())
    code_focus = []
    if str(task.get("scope") or "") == "code":
        area = str(assistant_action.get("target_area") or task.get("target_summary") or question or "").strip()
        if area:
            code_focus.append(_truncate(area, 140))
    payload = {
        "preferred_route_key": str(candidate_route.get("key") or current.get("preferred_route_key") or "").strip()[:64],
        "preferred_route_label": str(candidate_route.get("label") or current.get("preferred_route_label") or "").strip()[:120],
        "last_requested_module": str(candidate_route.get("label") or (page_context or {}).get("title") or (page_context or {}).get("page") or current.get("last_requested_module") or "").strip()[:120],
        "recent_destinations": ([str(candidate_route.get("label") or "").strip()] if candidate_route.get("label") else []) + current.get("recent_destinations", []),
        "successful_actions": successful + current.get("successful_actions", []),
        "code_focus_areas": code_focus + current.get("code_focus_areas", []),
        "recurring_intents": _bump_intent_counter(current.get("recurring_intents", []), str(planner.get("intent") or "")),
        "last_updated": _now_iso(),
    }
    _store_pref_value(workspace, _operator_profile_pref_key(actor_id), _normalize_operator_profile(payload))


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
    for key, limit in (("recent_issues", 12), ("recent_actions", 12), ("recent_successes", 12), ("recent_fixes", 12), ("recent_runbooks", 12), ("recent_questions", 10), ("recent_pages", 8)):
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


def _load_incident_ledger(workspace) -> list[dict]:
    payload = _pref_value(workspace, INCIDENT_LEDGER_PREF_KEY, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)][:60]


def _append_incident_ledger(workspace, entry: dict):
    if not workspace or not isinstance(entry, dict):
        return
    rows = _load_incident_ledger(workspace)
    rows.insert(0, {
        "created_at": str(entry.get("created_at") or _now_iso())[:64],
        "issue_id": str(entry.get("issue_id") or "").strip()[:120],
        "status": str(entry.get("status") or "").strip()[:32],
        "runbook": str(entry.get("runbook") or "").strip()[:64],
        "summary": _truncate(entry.get("summary"), 240),
        "kind": str(entry.get("kind") or "").strip()[:32],
    })
    _store_pref_value(workspace, INCIDENT_LEDGER_PREF_KEY, rows[:60])


def _runbook_execution_summary(runbook: dict | None, *, executed_tools=None, assistant_action=None, status: str = "", needs_confirmation: bool = False) -> dict:
    meta = dict(runbook or {})
    stages = [dict(row) for row in (meta.get("stages") or []) if isinstance(row, dict)]
    executions = [row for row in (executed_tools or []) if isinstance(row, dict)]
    if stages:
        stages[0]["done"] = True
    if len(stages) > 1 and (assistant_action or executions):
        stages[1]["done"] = True
    if len(stages) > 2 and ((assistant_action and assistant_action.get("success")) or any(bool(row.get("ok")) for row in executions)):
        stages[2]["done"] = True
    if stages and needs_confirmation:
        stages[-1]["done"] = False
    summary = []
    if assistant_action and assistant_action.get("success"):
        summary.append(str(assistant_action.get("kind") or "assistant_action"))
    for row in executions[:4]:
        if row.get("ok"):
            summary.append(str(row.get("tool") or "tool"))
    meta["stages"] = stages[:6]
    meta["execution_summary"] = summary[:6]
    meta["completed"] = not needs_confirmation and status in {"ok", "watch"} and any(stage.get("done") for stage in stages)
    return meta


def _store_memory(workspace, *, report: dict, response: dict, executed_tools: list[dict], question: str = "", page_context: dict | None = None, actor_id=None):
    if not workspace:
        return
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    summary = report.get("issue_summary") if isinstance(report.get("issue_summary"), dict) else {}
    current = _load_memory_for_actor(workspace, actor_id=actor_id)
    action_labels = [str(row.get("label") or row.get("tool") or "").strip() for row in executed_tools if isinstance(row, dict)]
    issue_labels = [str(row.get("id") or "").strip() for row in issues[:8] if isinstance(row, dict)]
    success_labels = [str(row.get("tool") or "").strip() for row in executed_tools if isinstance(row, dict) and row.get("ok")]
    fix_labels = [str(row.get("tool") or "").strip() for row in executed_tools if isinstance(row, dict) and row.get("ok") and str(row.get("kind") or "") in {"repair", "publish", "maintenance"}]
    runbook_label = str(((response.get("runbook") or {}).get("key") if isinstance(response.get("runbook"), dict) else "") or "").strip()
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
        "recent_fixes": ([x for x in fix_labels if x] + current.get("recent_fixes", []))[:12],
        "recent_runbooks": ([runbook_label] if runbook_label else []) + current.get("recent_runbooks", []),
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
            "recent_fixes": (payload.get("recent_fixes", []) + global_current.get("recent_fixes", []))[:12],
            "recent_runbooks": (payload.get("recent_runbooks", []) + global_current.get("recent_runbooks", []))[:12],
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


def _parse_session_request(question: str) -> dict:
    text = str(question or "").strip()
    lower = text.lower()
    focus = _extract_labeled_value(text, ["nombre", "focus", "titulo", "título"])
    if not focus:
        free_focus = re.search(
            r"(?:crea|crear|programa|planifica|monta|prepara)\s+(?:una\s+)?ses(?:i[oó]n)?(?:\s+de\s+entrenamiento)?\s+(.+?)(?=,| para | el | a las | hora| duración| intensidad| md| carga|$)",
            text,
            re.IGNORECASE,
        )
        focus = str(free_focus.group(1) if free_focus else "").strip(" .")
    date_raw = _extract_labeled_value(text, ["fecha", "día", "dia", "para el", "para"])
    if not date_raw:
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        date_raw = str(date_match.group(1) if date_match else "").strip()
    start_time_raw = _extract_labeled_value(text, ["hora", "a las", "inicio", "start"])
    if not start_time_raw:
        time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        start_time_raw = str(time_match.group(0) if time_match else "").strip()
    minutes_raw = _extract_labeled_value(text, ["duracion", "duración", "minutos", "minutes"])
    intensity = _extract_labeled_value(text, ["intensidad", "intensity"]).lower()
    notes = _extract_labeled_value(text, ["contenido", "notas", "notes", "objetivo"])
    if not notes and "objetivo" in lower:
        obj_match = re.search(r"objetivo\s*[:=]?\s*([^,;\n]+)", text, re.IGNORECASE)
        notes = str(obj_match.group(1) if obj_match else "").strip(" .")
    md_day = ""
    if "md-4" in lower:
        md_day = TrainingSession.DAY_MD_MINUS_4
    elif "md-3" in lower:
        md_day = TrainingSession.DAY_MD_MINUS_3
    elif "md-2" in lower:
        md_day = TrainingSession.DAY_MD_MINUS_2
    elif "md-1" in lower:
        md_day = TrainingSession.DAY_MD_MINUS_1
    elif re.search(r"\bmd\b", lower):
        md_day = TrainingSession.DAY_MD
    elif "md+1" in lower:
        md_day = TrainingSession.DAY_MD_PLUS_1
    elif "md+2" in lower:
        md_day = TrainingSession.DAY_MD_PLUS_2
    dominant_load = ""
    if "recuper" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_RECOVERY
    elif "tension" in lower or "tensión" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_TENSION
    elif "carga duracion" in lower or "carga duración" in lower or "dominant load: duration" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_DURATION
    elif "velocidad" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_SPEED
    elif "activacion" in lower or "activación" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_ACTIVATION
    elif "mixta" in lower or "mixto" in lower:
        dominant_load = TrainingSession.DOMINANT_LOAD_MIXED

    session_date = None
    if date_raw:
        match = re.search(r"\d{4}-\d{2}-\d{2}", date_raw)
        if match:
            try:
                session_date = datetime.strptime(match.group(0), "%Y-%m-%d").date()
            except ValueError:
                session_date = None
    start_time = None
    if start_time_raw:
        match = re.search(r"([01]?\d|2[0-3]):([0-5]\d)", start_time_raw)
        if match:
            try:
                start_time = datetime.strptime(match.group(0), "%H:%M").time()
            except ValueError:
                start_time = None
    duration_minutes = _safe_int(re.sub(r"[^\d]", "", minutes_raw), 0) if minutes_raw else 90
    if duration_minutes <= 0:
        duration_minutes = 90
    intensity_map = {
        "baja": TrainingSession.INTENSITY_LOW,
        "low": TrainingSession.INTENSITY_LOW,
        "media": TrainingSession.INTENSITY_MEDIUM,
        "medium": TrainingSession.INTENSITY_MEDIUM,
        "alta": TrainingSession.INTENSITY_HIGH,
        "high": TrainingSession.INTENSITY_HIGH,
        "recuperacion": TrainingSession.INTENSITY_RECOVERY,
        "recuperación": TrainingSession.INTENSITY_RECOVERY,
        "recovery": TrainingSession.INTENSITY_RECOVERY,
        "matchday": TrainingSession.INTENSITY_MATCHDAY,
        "prepartido": TrainingSession.INTENSITY_MATCHDAY,
    }
    intensity_value = intensity_map.get(intensity, TrainingSession.INTENSITY_MEDIUM)
    return {
        "focus": _truncate(focus, 140),
        "session_date": session_date,
        "start_time": start_time,
        "duration_minutes": max(30, min(duration_minutes, 180)),
        "intensity": intensity_value,
        "md_day": md_day,
        "dominant_load": dominant_load,
        "notes": _truncate(notes, 400),
    }


def _parse_task_request(question: str) -> dict:
    text = str(question or "").strip()
    lower = text.lower()
    title = _extract_labeled_value(text, ["titulo", "título", "nombre"])
    if not title:
        free_title = re.search(
            r"(?:crea|crear|genera|prepara|añade|agrega)\s+(?:una\s+)?tarea\s+(.+?)(?=,| con | para | objetivo| bloque| duraci[oó]n|minutos| repositorio| biblioteca|$)",
            text,
            re.IGNORECASE,
        )
        title = str(free_title.group(1) if free_title else "").strip(" .")
    title = re.sub(r"^(?:t[ií]tulo|titulo|nombre|tarea|task)\s*[:=]?\s*", "", str(title or ""), flags=re.IGNORECASE).strip(" .")
    objective = _extract_labeled_value(text, ["objetivo", "objetivos"])
    block = _extract_labeled_value(text, ["bloque", "fase", "block"])
    minutes_raw = _extract_labeled_value(text, ["duracion", "duración", "minutos", "minutes"])
    repository_raw = _extract_labeled_value(text, ["repositorio", "biblioteca", "repository"])
    repository_probe = f"{repository_raw} {text}".lower()
    if "ia trainer" in repository_probe or "ia-trainer" in repository_probe or "ai trainer" in repository_probe:
        repository = LIBRARY_REPOSITORY_AI_TRAINER
    elif "interactiva" in repository_probe or "interactive" in repository_probe:
        repository = LIBRARY_REPOSITORY_INTERACTIVE
    elif any(token in repository_probe for token in ["pdf", "tradicional", "clásica", "clasica"]):
        repository = LIBRARY_REPOSITORY_TRADITIONAL
    else:
        repository = normalize_library_repository(repository_raw or "")
        if repository not in {
            LIBRARY_REPOSITORY_TRADITIONAL,
            LIBRARY_REPOSITORY_INTERACTIVE,
            LIBRARY_REPOSITORY_AI_TRAINER,
        }:
            repository = LIBRARY_REPOSITORY_TRADITIONAL
    duration_minutes = _safe_int(re.sub(r"[^\d]", "", minutes_raw), 0) if minutes_raw else 12
    if duration_minutes <= 0:
        duration_minutes = 12
    return {
        "title": _truncate(title, 180),
        "objective": _truncate(objective, 300),
        "block": _truncate(block, 120),
        "duration_minutes": max(1, min(duration_minutes, 180)),
        "repository": repository,
        "scope_key": "coach",
    }


def _execute_create_session_action(question: str, *, workspace=None, page_context=None) -> dict:
    page_context = page_context if isinstance(page_context, dict) else {}
    payload = _parse_session_request(question)
    if not workspace:
        return {
            "kind": "create_session",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": ["contexto_equipo"],
            "message": "No puedo crear la sesión sin un workspace activo.",
            "payload": payload,
        }
    auth = _authorize_guard_action("create_session", page_context=page_context)
    if not auth.get("allowed"):
        return {
            "kind": "create_session",
            "executed": False,
            "success": False,
            "needs_input": False,
            "permission_required": True,
            "message": "Necesitas permisos de gestión para crear sesiones.",
            "authorization": auth,
            "payload": payload,
        }
    team_id = _safe_int(page_context.get("team_id"), 0)
    team = None
    if team_id and getattr(workspace, "teams", None) is not None:
        link = workspace.teams.select_related("team").filter(team_id=team_id).first()
        team = getattr(link, "team", None) if link else None
    if team is None:
        team = getattr(workspace, "primary_team", None)
    missing_fields = []
    if not payload.get("focus"):
        missing_fields.append("nombre_sesion")
    if not payload.get("session_date"):
        missing_fields.append("fecha")
    if not team:
        missing_fields.append("equipo")
    if missing_fields:
        return {
            "kind": "create_session",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": missing_fields,
            "message": "Pásame al menos nombre y fecha para crear la sesión.",
            "payload": payload,
        }
    microcycle = get_or_create_inbox_microcycle(team)
    if not microcycle:
        return {
            "kind": "create_session",
            "executed": False,
            "success": False,
            "needs_input": False,
            "message": "No pude preparar el microciclo base para guardar la sesión.",
            "payload": payload,
        }
    content = serialize_session_plan_fields({
        "notes": payload.get("notes") or "",
        "agenda_hidden": "",
    })
    with transaction.atomic():
        session = (
            TrainingSession.objects
            .filter(microcycle=microcycle, session_date=payload.get("session_date"), focus__iexact=str(payload.get("focus") or ""))
            .order_by("-id")
            .first()
        )
        created = session is None
        if created:
            next_order = (
                TrainingSession.objects.filter(microcycle=microcycle).order_by("-order").values_list("order", flat=True).first() or 0
            ) + 1
            session = TrainingSession.objects.create(
                microcycle=microcycle,
                club_season=_active_workspace_season(workspace),
                session_date=payload.get("session_date"),
                start_time=payload.get("start_time"),
                duration_minutes=payload.get("duration_minutes") or 90,
                intensity=payload.get("intensity") or TrainingSession.INTENSITY_MEDIUM,
                md_day=payload.get("md_day") or "",
                dominant_load=payload.get("dominant_load") or "",
                focus=str(payload.get("focus") or "")[:140],
                content=content,
                status=TrainingSession.STATUS_PLANNED,
                order=next_order,
            )
        else:
            updates = []
            for field in ("start_time", "duration_minutes", "intensity", "md_day", "dominant_load"):
                value = payload.get(field)
                if getattr(session, field) != value and value not in (None, ""):
                    setattr(session, field, value)
                    updates.append(field)
            if content and str(getattr(session, "content", "") or "").strip() != str(content).strip():
                session.content = content
                updates.append("content")
            if updates:
                session.save(update_fields=sorted(set(updates)))
    return {
        "kind": "create_session",
        "executed": True,
        "success": True,
        "needs_input": False,
        "message": (
            f"Sesión creada: {session.focus}."
            if created else f"Sesión actualizada: {session.focus}."
        ),
        "session": {
            "id": int(getattr(session, "id", 0) or 0),
            "focus": str(getattr(session, "focus", "") or ""),
            "date": str(getattr(session, "session_date", "") or ""),
            "team": str(getattr(team, "name", "") or ""),
            "duration_minutes": int(getattr(session, "duration_minutes", 0) or 0),
        },
        "payload": payload,
    }


def _execute_create_task_action(question: str, *, workspace=None, page_context=None) -> dict:
    page_context = page_context if isinstance(page_context, dict) else {}
    payload = _parse_task_request(question)
    if not workspace:
        return {
            "kind": "create_task",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": ["contexto_equipo"],
            "message": "No puedo crear la tarea sin un workspace activo.",
            "payload": payload,
        }
    auth = _authorize_guard_action("create_task", page_context=page_context)
    if not auth.get("allowed"):
        return {
            "kind": "create_task",
            "executed": False,
            "success": False,
            "needs_input": False,
            "permission_required": True,
            "message": "Necesitas permisos de gestión para crear tareas de biblioteca.",
            "authorization": auth,
            "payload": payload,
        }
    team_id = _safe_int(page_context.get("team_id"), 0)
    team = None
    if team_id and getattr(workspace, "teams", None) is not None:
        link = workspace.teams.select_related("team").filter(team_id=team_id).first()
        team = getattr(link, "team", None) if link else None
    if team is None:
        team = getattr(workspace, "primary_team", None)
    missing_fields = []
    if not payload.get("title"):
        missing_fields.append("titulo_tarea")
    if not team:
        missing_fields.append("equipo")
    if missing_fields:
        return {
            "kind": "create_task",
            "executed": False,
            "success": False,
            "needs_input": True,
            "missing_fields": missing_fields,
            "message": "Pásame al menos el nombre de la tarea para guardarla en biblioteca.",
            "payload": payload,
        }
    library_session = get_or_create_library_session_with_repository(
        team,
        str(payload.get("scope_key") or "coach"),
        repository=str(payload.get("repository") or LIBRARY_REPOSITORY_TRADITIONAL),
    )
    if not library_session:
        return {
            "kind": "create_task",
            "executed": False,
            "success": False,
            "needs_input": False,
            "message": "No pude preparar la biblioteca donde guardar la tarea.",
            "payload": payload,
        }
    with transaction.atomic():
        task = (
            SessionTask.objects
            .filter(session=library_session, title__iexact=str(payload.get("title") or ""))
            .order_by("-id")
            .first()
        )
        created = task is None
        next_order = (
            SessionTask.objects.filter(session=library_session).order_by("-order").values_list("order", flat=True).first() or 0
        ) + 1
        meta = {
            "scope": str(payload.get("scope_key") or "coach"),
            "source": "manual-chat",
            "repository": str(payload.get("repository") or LIBRARY_REPOSITORY_TRADITIONAL),
            "is_template": True,
        }
        if created:
            task = SessionTask.objects.create(
                session=library_session,
                title=str(payload.get("title") or "")[:180],
                block=str(payload.get("block") or "")[:120],
                duration_minutes=int(payload.get("duration_minutes") or 12),
                objective=str(payload.get("objective") or "")[:300],
                status="draft",
                order=next_order,
                tactical_layout={"meta": meta},
            )
        else:
            updates = []
            for field in ("block", "objective"):
                value = str(payload.get(field) or "")
                value = value[:120] if field == "block" else value[:300]
                if value and getattr(task, field) != value:
                    setattr(task, field, value)
                    updates.append(field)
            duration_value = int(payload.get("duration_minutes") or 12)
            if int(getattr(task, "duration_minutes", 0) or 0) != duration_value:
                task.duration_minutes = duration_value
                updates.append("duration_minutes")
            tactical_layout = getattr(task, "tactical_layout", None)
            if not isinstance(tactical_layout, dict):
                tactical_layout = {}
            if tactical_layout.get("meta") != meta:
                tactical_layout["meta"] = meta
                task.tactical_layout = tactical_layout
                updates.append("tactical_layout")
            if updates:
                task.save(update_fields=sorted(set(updates)))
    return {
        "kind": "create_task",
        "executed": True,
        "success": True,
        "needs_input": False,
        "message": (
            f"Tarea creada en biblioteca: {task.title}."
            if created else f"Tarea actualizada en biblioteca: {task.title}."
        ),
        "task": {
            "id": int(getattr(task, "id", 0) or 0),
            "title": str(getattr(task, "title", "") or ""),
            "repository": str(payload.get("repository") or LIBRARY_REPOSITORY_TRADITIONAL),
            "duration_minutes": int(getattr(task, "duration_minutes", 0) or 0),
            "session": str(getattr(library_session, "focus", "") or ""),
            "team": str(getattr(team, "name", "") or ""),
        },
        "payload": payload,
    }


def _execute_navigation_action(question: str, *, page_context=None) -> dict:
    route = _match_route_target(question, page_context=page_context)
    if not isinstance(route, dict) or not route.get("url"):
        return {
            "kind": "navigate_module",
            "executed": False,
            "success": False,
            "needs_input": True,
            "message": "No he identificado con precisión la pantalla destino. Dime el módulo y te llevo.",
        }
    return {
        "kind": "navigate_module",
        "executed": True,
        "success": True,
        "needs_input": False,
        "message": f"Te llevo a {str(route.get('label') or 'la pantalla solicitada')}.",
        "navigate_to": {
            "key": str(route.get("key") or ""),
            "label": str(route.get("label") or ""),
            "url": str(route.get("url") or ""),
        },
    }


def _execute_guidance_action(question: str, *, page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    page_label = str(context.get("title") or context.get("page") or "esta pantalla").strip()
    route_rows = _guard_route_catalog(page_context)
    suggestions = [str(row.get("label") or "") for row in route_rows[:3] if str(row.get("label") or "").strip()]
    return {
        "kind": "guide_user",
        "executed": True,
        "success": True,
        "needs_input": False,
        "message": f"Te guío sobre {page_label}. Puedo explicarte la pantalla actual o llevarte a otro módulo.",
        "guidance": {
            "page": page_label,
            "next_modules": suggestions[:3],
            "question": _truncate(question, 160),
        },
    }


def _capability_snapshot(*, page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    can_code = bool(context.get("can_operate_guard_code"))
    visible = []
    for row in OLLANA_CAPABILITIES.get("skills") or []:
        if bool(row.get("requires_code_operator")) and not can_code:
            continue
        visible.append({
            "key": str(row.get("key") or ""),
            "label": str(row.get("label") or ""),
            "scope": str(row.get("scope") or ""),
        })
    permission_profile = _permission_profile(page_context=page_context)
    return {
        "identity": dict(OLLANA_CAPABILITIES.get("identity") or {}),
        "modes": dict(OLLANA_CAPABILITIES.get("modes") or {}),
        "skills": visible[:12],
        "permissions": permission_profile,
    }


def _execution_surface_snapshot(*, page_context=None) -> dict:
    permissions = _permission_profile(page_context=page_context)
    rows = []
    visible_skills = _capability_snapshot(page_context=page_context).get("skills") or []
    visible_keys = {str(row.get("key") or "") for row in visible_skills if isinstance(row, dict)}
    for surface, skill_keys in OLLANA_ACTION_SURFACES.items():
        rows.append({
            "surface": str(surface),
            "skills": [key for key in skill_keys if key in visible_keys],
            "count": len([key for key in skill_keys if key in visible_keys]),
        })
    return {
        "surfaces": rows,
        "permissions": permissions,
    }


def _action_catalog_snapshot(*, page_context=None) -> dict:
    rows = []
    for action_key, policy in ACTION_PERMISSION_MATRIX.items():
        auth = _authorize_guard_action(action_key, page_context=page_context)
        rows.append({
            "key": str(action_key),
            "scope": str((auth.get("policy") or {}).get("scope") or ""),
            "allowed": bool(auth.get("allowed")),
            "requires_manage_guard": bool((auth.get("policy") or {}).get("requires_manage_guard")),
            "requires_code_operator": bool((auth.get("policy") or {}).get("requires_code_operator")),
        })
    grouped = {}
    for row in rows:
        grouped.setdefault(str(row.get("scope") or "other"), []).append(row)
    return {
        "items": rows,
        "groups": grouped,
    }


def _governance_snapshot(*, page_context=None, planner=None, technical_operation=None) -> dict:
    planner = planner if isinstance(planner, dict) else {}
    technical_operation = technical_operation if isinstance(technical_operation, dict) else {}
    permissions = _permission_profile(page_context=page_context)
    confirmation_required = bool(planner.get("confirm_required"))
    return {
        "permissions": permissions,
        "confirmation_required": confirmation_required,
        "publish_requires_confirmation": bool(technical_operation.get("publish_requires_confirmation")),
        "authorized_for_code": bool(technical_operation.get("authorized_for_code")),
        "authorized_for_publish": bool(technical_operation.get("authorized_for_publish")),
        "auditable": True,
    }


def _policy_decisions_snapshot(*, page_context=None, planner=None, assistant_action=None, technical_operation=None) -> dict:
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    technical_operation = technical_operation if isinstance(technical_operation, dict) else {}
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    action_kind = str(assistant_action.get("kind") or "")
    requested_action = "inspect_system"
    if action_kind == "navigate_module":
        requested_action = "navigate_modules"
    elif action_kind == "guide_user":
        requested_action = "guide_user"
    elif action_kind == "create_player":
        requested_action = "create_player"
    elif action_kind == "create_session":
        requested_action = "create_session"
    elif action_kind == "create_task":
        requested_action = "create_task"
    elif str(technical_operation.get("kind") or "") == "technical_operation":
        requested_action = "repair_code"
    elif str(task.get("scope") or "") == "code":
        requested_action = "inspect_repo"
    requested_auth = _authorize_guard_action(requested_action, page_context=page_context)
    publish_auth = _authorize_guard_action("publish_changes", page_context=page_context)
    return {
        "requested_action": requested_action,
        "requested_action_allowed": bool(requested_auth.get("allowed")),
        "requested_action_reasons": list(requested_auth.get("reasons") or []),
        "publish_allowed": bool(publish_auth.get("allowed")),
        "confirm_required": bool(planner.get("confirm_required")),
    }


def _orchestration_snapshot(question: str, *, planner=None, assistant_action=None, code_operator_mode=None) -> dict:
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    code_operator_mode = code_operator_mode if isinstance(code_operator_mode, dict) else {}
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    return {
        "intent": str(planner.get("intent") or ""),
        "task_kind": str(task.get("kind") or ""),
        "task_scope": str(task.get("scope") or ""),
        "silent_mode": bool(task.get("silent_mode")),
        "runbook": str((planner.get("runbook") or {}).get("key") or ""),
        "target_summary": _truncate(question, 220),
        "assistant_action_kind": str(assistant_action.get("kind") or ""),
        "code_mode": str(code_operator_mode.get("mode") or ""),
        "requested_tools": [str(item) for item in (planner.get("requested_tools") or []) if str(item or "").strip()][:8],
    }


def _execution_plan_snapshot(*, planner=None, assistant_action=None, technical_operation=None, technical_execution=None, change_blueprint=None) -> dict:
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    technical_operation = technical_operation if isinstance(technical_operation, dict) else {}
    technical_execution = technical_execution if isinstance(technical_execution, dict) else {}
    change_blueprint = change_blueprint if isinstance(change_blueprint, dict) else {}
    stages = []
    for row in (planner.get("steps") or [])[:6]:
        if not isinstance(row, dict):
            continue
        stages.append({
            "step": str(row.get("step") or ""),
            "done": bool(row.get("done")),
        })
    if str(technical_operation.get("kind") or "") == "technical_operation":
        for phase in (technical_operation.get("phases") or [])[:5]:
            if not isinstance(phase, dict):
                continue
            stages.append({
                "step": str(phase.get("label") or phase.get("key") or ""),
                "done": str(phase.get("key") or "") in {str(item) for item in (technical_execution.get("completed_phases") or [])},
            })
    return {
        "target": str((change_blueprint.get("target") or assistant_action.get("message") or "") or "")[:220],
        "assistant_action_kind": str(assistant_action.get("kind") or ""),
        "status": str(technical_execution.get("status") or ("completed" if assistant_action.get("success") else "pending")),
        "publish_ready": bool(technical_execution.get("publish_ready")),
        "stages": stages[:10],
    }


def _system_knowledge_snapshot(*, page_context=None) -> dict:
    modules = _module_inventory()
    routes = _route_inventory()
    assets = _asset_inventory()
    env = _environment_snapshot()
    repo = _inspect_repo_status()
    module_rows = []
    for key, row in modules.items():
        if not isinstance(row, dict):
            continue
        module_rows.append({
            "key": str(key),
            "label": str(row.get("label") or key),
            "kind": str(row.get("kind") or ""),
            "available": bool(row.get("available", row.get("exists", False))),
        })
    route_rows = []
    for key, row in routes.items():
        if not isinstance(row, dict):
            continue
        route_rows.append({
            "key": str(key),
            "label": str(row.get("label") or key),
            "name": str(row.get("name") or ""),
            "ok": bool(row.get("ok")),
            "url": str(row.get("url") or "")[:220],
        })
    asset_rows = []
    for key, row in assets.items():
        if not isinstance(row, dict):
            continue
        asset_rows.append({
            "key": str(key),
            "label": str(row.get("label") or key),
            "ok": bool(row.get("ok")),
            "size": _safe_int(row.get("size"), 0),
        })
    return {
        "workspace_page": str((page_context or {}).get("page") or "")[:120],
        "environment": {
            "debug": bool(env.get("debug")),
            "base_dir": str(env.get("base_dir") or "")[:220],
            "database_engine": str(env.get("database_engine") or "")[:160],
            "static_root": str(env.get("static_root") or "")[:220],
            "media_root": str(env.get("media_root") or "")[:220],
        },
        "module_count": len(module_rows),
        "route_count": len(route_rows),
        "asset_count": len(asset_rows),
        "modules": module_rows[:8],
        "critical_routes": route_rows[:8],
        "critical_assets": asset_rows[:8],
        "repo": {
            "available": bool(repo.get("ok")),
            "branch": str(repo.get("branch") or "")[:120],
            "changed_count": _safe_int(repo.get("changed_count"), 0),
            "last_commit": str(repo.get("last_commit") or "")[:220],
        },
    }


def _presence_snapshot(*, page_context=None, planner=None, assistant_action=None, operator_profile=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    operator_profile = operator_profile if isinstance(operator_profile, dict) else {}
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    active_page = str(context.get("title") or context.get("page") or "").strip()[:120]
    active_path = str(context.get("path") or "").strip()[:220]
    active_team_id = _safe_int(context.get("team_id"), 0)
    active_workspace_id = _safe_int(context.get("workspace_id"), 0)
    route_rows = _guard_route_catalog(page_context)
    current_target = task.get("route_target") if isinstance(task.get("route_target"), dict) else {}
    if isinstance(assistant_action.get("navigate_to"), dict) and assistant_action.get("navigate_to", {}).get("key"):
        current_target = assistant_action.get("navigate_to")
    nearby = []
    for row in route_rows[:5]:
        if not isinstance(row, dict):
            continue
        nearby.append({
            "key": str(row.get("key") or ""),
            "label": str(row.get("label") or "")[:120],
            "url": str(row.get("url") or "")[:220],
        })
    return {
        "active_page": active_page,
        "active_path": active_path,
        "active_team_id": active_team_id,
        "active_workspace_id": active_workspace_id,
        "current_target": {
            "key": str(current_target.get("key") or ""),
            "label": str(current_target.get("label") or "")[:120],
            "url": str(current_target.get("url") or "")[:220],
        },
        "nearby_modules": nearby,
        "preferred_route": str(operator_profile.get("preferred_route_label") or "")[:120],
        "inside_system": bool(active_page or active_workspace_id or active_team_id),
    }


def _domain_context_snapshot(workspace, *, page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    team_id = _safe_int(context.get("team_id"), 0)
    workspace_id = _safe_int(context.get("workspace_id"), 0)
    active_team = None
    active_season = _active_workspace_season(workspace)
    competition_context = None
    if workspace:
        team_link_qs = workspace.teams.select_related("team", "team__group__season__competition")
        if team_id:
            team_link = team_link_qs.filter(team_id=team_id).first()
        else:
            team_link = team_link_qs.filter(is_default=True).first() or team_link_qs.first()
        active_team = getattr(team_link, "team", None) if team_link else getattr(workspace, "primary_team", None)
        if active_team:
            competition_context = WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=active_team).first()
    team_group = getattr(active_team, "group", None) if active_team else None
    team_season = getattr(team_group, "season", None) if team_group else None
    team_competition = getattr(team_season, "competition", None) if team_season else None
    roster_count = 0
    session_count = 0
    task_count = 0
    if active_team:
        roster_count = Player.objects.filter(team=active_team, is_active=True).count()
        session_count = TrainingSession.objects.filter(microcycle__team=active_team).count()
        task_count = SessionTask.objects.filter(session__microcycle__team=active_team, deleted_at__isnull=True).count()
    workspace_team_count = workspace.teams.count() if workspace else 0
    workspace_player_count = workspace.players.filter(is_active=True).count() if workspace and getattr(workspace, "players", None) is not None else 0
    return {
        "workspace": {
            "id": int(getattr(workspace, "id", 0) or workspace_id or 0),
            "name": str(getattr(workspace, "name", "") or "")[:160],
            "kind": str(getattr(workspace, "kind", "") or "")[:32],
            "team_count": workspace_team_count,
            "player_count": workspace_player_count,
        },
        "team": {
            "id": int(getattr(active_team, "id", 0) or team_id or 0),
            "name": str(getattr(active_team, "display_name", "") or getattr(active_team, "name", "") or "")[:160],
            "category": str(getattr(active_team, "category", "") or "")[:80],
            "roster_count": roster_count,
            "session_count": session_count,
            "task_count": task_count,
        },
        "season": {
            "workspace_label": str(getattr(active_season, "label", "") or "")[:80],
            "competition_label": str(getattr(team_season, "name", "") or "")[:120],
            "competition_name": str(getattr(team_competition, "name", "") or "")[:120],
            "is_active": bool(getattr(active_season, "is_active", False)),
        },
        "competition_context": {
            "provider": str(getattr(competition_context, "provider", "") or "")[:32],
            "status": str(getattr(competition_context, "sync_status", "") or "")[:32],
            "external_team_name": str(getattr(competition_context, "external_team_name", "") or "")[:160],
            "auto_sync": bool(getattr(competition_context, "is_auto_sync_enabled", False)),
        },
        "inside_workspace": bool(workspace),
    }


def _runtime_business_snapshot(workspace, *, page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    team_id = _safe_int(context.get("team_id"), 0)
    library_repo = normalize_library_repository(str(context.get("library_repo") or context.get("repository") or "").strip())
    active_team = None
    if workspace:
        team_link_qs = workspace.teams.select_related("team")
        if team_id:
            team_link = team_link_qs.filter(team_id=team_id).first()
        else:
            team_link = team_link_qs.filter(is_default=True).first() or team_link_qs.first()
        active_team = getattr(team_link, "team", None) if team_link else getattr(workspace, "primary_team", None)
    today = datetime.now(timezone.utc).date()
    current_microcycle = None
    next_session = None
    latest_session = None
    library_task_count = 0
    if active_team:
        current_microcycle = (
            active_team.microcycles
            .filter(week_start__lte=today, week_end__gte=today)
            .order_by("-week_start", "-id")
            .first()
        )
        next_session = (
            TrainingSession.objects
            .select_related("microcycle")
            .filter(microcycle__team=active_team, session_date__gte=today)
            .order_by("session_date", "start_time", "order", "id")
            .first()
        )
        latest_session = (
            TrainingSession.objects
            .select_related("microcycle")
            .filter(microcycle__team=active_team)
            .order_by("-session_date", "-start_time", "-order", "-id")
            .first()
        )
        library_task_qs = SessionTask.objects.filter(session__microcycle__team=active_team, deleted_at__isnull=True)
        if library_repo:
            repo_token = str(library_repo).strip().lower()
            library_task_qs = library_task_qs.filter(tactical_layout__meta__repository=repo_token)
        library_task_count = library_task_qs.count()
    return {
        "active_team_id": int(getattr(active_team, "id", 0) or team_id or 0),
        "current_microcycle": {
            "id": int(getattr(current_microcycle, "id", 0) or 0),
            "title": str(getattr(current_microcycle, "title", "") or "")[:160],
            "week_start": str(getattr(current_microcycle, "week_start", "") or "")[:32],
            "week_end": str(getattr(current_microcycle, "week_end", "") or "")[:32],
        },
        "next_session": {
            "id": int(getattr(next_session, "id", 0) or 0),
            "focus": str(getattr(next_session, "focus", "") or "")[:140],
            "date": str(getattr(next_session, "session_date", "") or "")[:32],
            "duration_minutes": _safe_int(getattr(next_session, "duration_minutes", 0), 0),
        },
        "latest_session": {
            "id": int(getattr(latest_session, "id", 0) or 0),
            "focus": str(getattr(latest_session, "focus", "") or "")[:140],
            "date": str(getattr(latest_session, "session_date", "") or "")[:32],
            "duration_minutes": _safe_int(getattr(latest_session, "duration_minutes", 0), 0),
        },
        "library_repository": library_repo,
        "library_task_count": library_task_count,
        "page_tab": str(context.get("tab") or "")[:64],
    }


def _live_workflow_snapshot(workspace, *, page_context=None) -> dict:
    context = page_context if isinstance(page_context, dict) else {}
    session_id = _safe_int(context.get("session_id") or context.get("selected_session_id"), 0)
    task_id = _safe_int(context.get("task_id") or context.get("source_task_id"), 0)
    match_id = _safe_int(context.get("match_id"), 0)
    microcycle_id = _safe_int(context.get("microcycle_id") or context.get("prefill_microcycle_id"), 0)
    selected_session = None
    selected_task = None
    active_match = None
    selected_microcycle = None
    if session_id:
        selected_session = TrainingSession.objects.select_related("microcycle", "microcycle__team").filter(id=session_id).first()
    if task_id:
        selected_task = SessionTask.objects.select_related("session", "session__microcycle", "session__microcycle__team").filter(id=task_id).first()
    if match_id:
        active_match = Match.objects.select_related("home_team", "away_team").filter(id=match_id).first()
    if microcycle_id:
        selected_microcycle = TrainingMicrocycle.objects.select_related("team").filter(id=microcycle_id).first()
    if selected_microcycle is None and selected_session is not None:
        selected_microcycle = getattr(selected_session, "microcycle", None)
    if selected_session is None and selected_task is not None:
        selected_session = getattr(selected_task, "session", None)
    return {
        "page_tab": str(context.get("tab") or "")[:64],
        "selected_session": {
            "id": int(getattr(selected_session, "id", 0) or 0),
            "focus": str(getattr(selected_session, "focus", "") or "")[:140],
            "date": str(getattr(selected_session, "session_date", "") or "")[:32],
        },
        "selected_task": {
            "id": int(getattr(selected_task, "id", 0) or 0),
            "title": str(getattr(selected_task, "title", "") or "")[:180],
            "duration_minutes": _safe_int(getattr(selected_task, "duration_minutes", 0), 0),
        },
        "selected_microcycle": {
            "id": int(getattr(selected_microcycle, "id", 0) or 0),
            "title": str(getattr(selected_microcycle, "title", "") or "")[:160],
            "week_start": str(getattr(selected_microcycle, "week_start", "") or "")[:32],
        },
        "active_match": {
            "id": int(getattr(active_match, "id", 0) or 0),
            "home_team": str(getattr(getattr(active_match, "home_team", None), "name", "") or "")[:120],
            "away_team": str(getattr(getattr(active_match, "away_team", None), "name", "") or "")[:120],
            "date": str(getattr(active_match, "date", "") or "")[:32],
        },
        "is_focused_context": bool(selected_session or selected_task or active_match or selected_microcycle),
    }


def _mission_control_snapshot(
    workspace,
    *,
    page_context=None,
    planner=None,
    assistant_action=None,
    technical_execution=None,
    silent_operator=None,
    improvement_proposals=None,
    snapshot_diff=None,
) -> dict:
    observability = _observability_summary(workspace) if workspace else {}
    planner = planner if isinstance(planner, dict) else {}
    assistant_action = assistant_action if isinstance(assistant_action, dict) else {}
    technical_execution = technical_execution if isinstance(technical_execution, dict) else {}
    silent_operator = silent_operator if isinstance(silent_operator, dict) else {}
    snapshot_diff = snapshot_diff if isinstance(snapshot_diff, dict) else {}
    improvement_proposals = improvement_proposals if isinstance(improvement_proposals, list) else []
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    runbook = planner.get("runbook") if isinstance(planner.get("runbook"), dict) else {}
    alerts = []
    for row in (observability.get("alerts") or [])[:3]:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if text:
            alerts.append(text[:180])
    for row in (snapshot_diff.get("regressions") or [])[:2]:
        label = str(row or "").strip()
        if label:
            alerts.append(f"Regresión: {label}"[:180])
    if assistant_action.get("permission_required"):
        alerts.append("Hay una acción bloqueada por permisos.")
    priority_queue = []
    for row in improvement_proposals[:4]:
        if not isinstance(row, dict):
            continue
        priority_queue.append({
            "title": str(row.get("title") or "")[:140],
            "priority": str(row.get("priority") or "next")[:24],
            "kind": str(row.get("kind") or "assistant")[:32],
        })
    recommended = []
    for row in (silent_operator.get("suggested_actions") or [])[:2]:
        label = str(row or "").strip()
        if label:
            recommended.append(label[:160])
    for row in improvement_proposals[:3]:
        if not isinstance(row, dict):
            continue
        label = str(row.get("title") or "").strip()
        if label and label not in recommended:
            recommended.append(label[:160])
    page = str((page_context or {}).get("page") or "").strip()[:120] if isinstance(page_context, dict) else ""
    return {
        "embedded": True,
        "role": "central_system_intelligence",
        "active_page": page,
        "system_health": str(observability.get("health_state") or "amber")[:24],
        "llm_stability": str(observability.get("llm_stability") or "unknown")[:24],
        "active_mission": {
            "task_kind": str(task.get("kind") or "")[:32],
            "scope": str(task.get("scope") or "")[:32],
            "runbook": str(runbook.get("key") or task.get("runbook_key") or "")[:64],
            "target": str(task.get("target_summary") or "")[:220],
        },
        "autonomy": {
            "silent_mode": bool(task.get("silent_mode")),
            "publish_ready": bool(technical_execution.get("publish_ready")),
            "queue_pending": _safe_int((silent_operator.get("queue_counts") or {}).get("pending"), 0),
            "queue_blocked": _safe_int((silent_operator.get("queue_counts") or {}).get("blocked"), 0),
            "continuous_enabled": bool(silent_operator.get("continuous_enabled")),
        },
        "alerts": alerts[:4],
        "priority_queue": priority_queue,
        "recommended_next_actions": recommended[:4],
    }


def _build_intelligence_os_snapshot(
    question: str,
    *,
    workspace=None,
    page_context=None,
    planner=None,
    assistant_action=None,
    technical_operation=None,
    technical_execution=None,
    code_operator_mode=None,
    change_blueprint=None,
    autofix_runner=None,
    operator_profile=None,
    silent_operator=None,
    improvement_proposals=None,
    snapshot_diff=None,
) -> dict:
    technical_execution = technical_execution if isinstance(technical_execution, dict) else {}
    change_blueprint = change_blueprint if isinstance(change_blueprint, dict) else {}
    autofix_runner = autofix_runner if isinstance(autofix_runner, dict) else {}
    operator_profile = operator_profile if isinstance(operator_profile, dict) else {}
    silent_operator = silent_operator if isinstance(silent_operator, dict) else {}
    improvement_proposals = improvement_proposals if isinstance(improvement_proposals, list) else []
    snapshot_diff = snapshot_diff if isinstance(snapshot_diff, dict) else {}
    return {
        "version": OLLANA_SYSTEM_OS_VERSION,
        "layers": {
            "conversation": {
                "enabled": True,
                "guided_assistant": True,
                "widget_expected": True,
            },
            "knowledge": _system_knowledge_snapshot(page_context=page_context),
            "domain": _domain_context_snapshot(workspace, page_context=page_context),
            "runtime": _runtime_business_snapshot(workspace, page_context=page_context),
            "live_workflow": _live_workflow_snapshot(workspace, page_context=page_context),
            "mission_control": _mission_control_snapshot(
                workspace,
                page_context=page_context,
                planner=planner,
                assistant_action=assistant_action,
                technical_execution=technical_execution,
                silent_operator=silent_operator,
                improvement_proposals=improvement_proposals,
                snapshot_diff=snapshot_diff,
            ),
            "presence": _presence_snapshot(
                page_context=page_context,
                planner=planner,
                assistant_action=assistant_action,
                operator_profile=operator_profile,
            ),
            "orchestration": _orchestration_snapshot(
                question,
                planner=planner,
                assistant_action=assistant_action,
                code_operator_mode=code_operator_mode,
            ),
            "execution": {
                "surface": _execution_surface_snapshot(page_context=page_context),
                "action_catalog": _action_catalog_snapshot(page_context=page_context),
                "assistant_action_kind": str((assistant_action or {}).get("kind") or ""),
                "technical_execution_status": str(technical_execution.get("status") or ""),
                "publish_ready": bool(technical_execution.get("publish_ready")),
                "execution_plan": _execution_plan_snapshot(
                    planner=planner,
                    assistant_action=assistant_action,
                    technical_operation=technical_operation,
                    technical_execution=technical_execution,
                    change_blueprint=change_blueprint,
                ),
                "autofix_runner": autofix_runner,
            },
            "supervision": {
                "silent_operator": silent_operator,
                "change_blueprint_enabled": bool(change_blueprint.get("enabled")),
                "change_targets": len(change_blueprint.get("file_changes") or []),
            },
            "governance": _governance_snapshot(
                page_context=page_context,
                planner=planner,
                technical_operation=technical_operation,
            ),
            "policy_decisions": _policy_decisions_snapshot(
                page_context=page_context,
                planner=planner,
                assistant_action=assistant_action,
                technical_operation=technical_operation,
            ),
            "memory": operator_profile,
        },
    }


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
    auth = _authorize_guard_action("create_player", page_context=page_context)
    if not auth.get("allowed"):
        return {
            "kind": "create_player",
            "executed": False,
            "success": False,
            "needs_input": False,
            "permission_required": True,
            "message": "Necesitas permisos de gestión para modificar la plantilla.",
            "authorization": auth,
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


def _infer_code_area(question: str, *, page_context=None) -> dict:
    text = str(question or "").strip().lower()
    page = str((page_context or {}).get("page") or "").strip().lower()
    area = "Código de la aplicación"
    candidate_files: list[str] = []
    suggested_checks: list[str] = []

    def add_file(path: str):
        cleaned = str(path or "").strip()
        if cleaned and cleaned not in candidate_files:
            candidate_files.append(cleaned)

    def add_check(label: str):
        cleaned = str(label or "").strip()
        if cleaned and cleaned not in suggested_checks:
            suggested_checks.append(cleaned)

    if any(token in text for token in ["3d", "pitch3d", "estadio", "stadium", "glb", "render", "canvas", "visualiza"]):
        area = "Render 3D del estadio y editor táctico"
        add_file("football/static/football/js/sessions_tactical_pad.js")
        add_file("football/views.py")
        add_file("football/templates/football/task_builder.html")
        add_check("Comprobar si cargan el modelo GLB, texturas y assets del estadio.")
        add_check("Revisar la inicialización del renderer 3D y el montaje del canvas táctico.")
        add_check("Ejecutar el smoke del task builder y revisar errores de consola/render.")

    if any(token in text for token in ["chat", "widget", "ollana", "guard", "asistente"]):
        area = "Widget conversacional y flujo del guard"
        add_file("football/templates/football/includes/global_guard_widget.html")
        add_file("football/system_guard.py")
        add_check("Verificar el ciclo abrir/cerrar del widget y la respuesta del chat.")
        add_check("Comprobar timeouts, fetch del endpoint y render del estado pendiente.")

    if any(token in text for token in ["ia trainer", "ai trainer", "trainer"]):
        add_file("football/templates/football/ai_trainer.html")
        add_file("football/views.py")
        add_check("Revisar contexto de página y montaje del guard dentro de IA Trainer.")

    if page in {"sessions-task-create", "task_builder"}:
        area = "Editor de tareas y capa visual del task builder"
        add_file("football/templates/football/task_builder.html")
        add_file("football/static/football/js/sessions_tactical_pad.js")
        add_check("Validar el render del editor en la pantalla de creación de tareas.")

    if not candidate_files:
        add_file("football/system_guard.py")
        add_check("Inspeccionar el diff, los errores recientes y la validación técnica del repositorio.")

    return {
        "area": area,
        "candidate_files": candidate_files[:6],
        "suggested_checks": suggested_checks[:4],
        "summary": _truncate(question, 220),
        "page": page,
    }


def _build_code_intervention_request(question: str, *, workspace=None, page_context=None) -> dict:
    detail = _infer_code_area(question, page_context=page_context)
    auth = _authorize_guard_action("repair_code", page_context=page_context)
    publish_auth = _authorize_guard_action("publish_changes", page_context=page_context)
    catalog_candidates = _catalog_candidates_for_question(question)
    allowed = bool(auth.get("allowed"))
    area = str(detail.get("area") or "código de la aplicación")
    file_list = [str(item) for item in (detail.get("candidate_files") or []) if str(item or "").strip()]
    check_list = [str(item) for item in (detail.get("suggested_checks") or []) if str(item or "").strip()]
    message = (
        f"He preparado una intervención técnica sobre {area.lower()}."
        if allowed else
        f"He preparado la intervención técnica para {area.lower()}, pero este usuario no tiene permiso para tocar código."
    )
    if file_list:
        message += f" Empezaría por {', '.join(file_list[:2])}."
    return {
        "kind": "code_intervention_request",
        "executed": False,
        "success": False,
        "needs_input": False,
        "permission_required": not allowed,
        "requires_operator_flow": True,
        "message": message,
        "target": str(detail.get("summary") or ""),
        "target_area": area,
        "candidate_files": file_list,
        "suggested_checks": check_list,
        "catalog_candidates": catalog_candidates,
        "authorization": auth,
        "publish_authorization": publish_auth,
        "payload": {
            "target": str(detail.get("summary") or ""),
            "area": area,
            "candidate_files": file_list,
            "suggested_checks": check_list,
            "catalog_candidates": catalog_candidates,
            "workspace_id": int(getattr(workspace, "id", 0) or 0) if workspace else 0,
            "page": str(detail.get("page") or ""),
        },
    }


def _build_code_operator_mode(question: str, planner: dict, *, page_context=None) -> dict:
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    if str(task.get("scope") or "") != "code":
        return {}
    detail = _infer_code_area(question, page_context=page_context)
    route_target = task.get("route_target") if isinstance(task.get("route_target"), dict) else {}
    question_text = str(question or "").strip()
    question_lower = question_text.lower()
    auth = _authorize_guard_action("repair_code", page_context=page_context)
    publish_auth = _authorize_guard_action("publish_changes", page_context=page_context)
    requested_tools = [str(item) for item in (planner.get("requested_tools") or []) if str(item or "").strip()]
    mode = "repair" if str(planner.get("intent") or "") == "repair" else ("build" if str(planner.get("intent") or "") == "feature_request" else "code_workflow")
    objectives = []
    if mode == "build":
        objectives.append(f"Implementar: {_truncate(question_text, 180)}")
        objectives.append("Localizar el punto de entrada funcional y definir el alcance mínimo viable.")
        objectives.append("Validar que el cambio no rompe flujos existentes.")
    elif mode == "repair":
        objectives.append(f"Corregir: {_truncate(question_text, 180)}")
        objectives.append("Aislar la causa raíz antes de tocar código.")
        objectives.append("Validar el arreglo y preparar publicación si procede.")
    else:
        objectives.append(f"Revisar flujo técnico: {_truncate(question_text, 180)}")
        objectives.append("Inspeccionar el repositorio y proponer el cambio correcto.")
    constraints = [
        "No tocar código fuera del alcance identificado.",
        "Ejecutar validación antes de publicar.",
        "Mantener trazabilidad en cola y auditoría.",
    ]
    if route_target.get("url"):
        constraints.append(f"Preservar la navegación de {route_target.get('label')}.")
    if "3d" in question_lower or "pitch3d" in question_lower or "estadio" in question_lower:
        constraints.append("No degradar el render 3D ni la pizarra táctica.")
    change_plan = [
        {"step": "Inspeccionar archivos candidatos y contexto de pantalla.", "status": "pending"},
        {"step": "Definir cambio mínimo viable o fix concreto.", "status": "pending"},
        {"step": "Aplicar intervención segura o dejar blueprint exacto de edición.", "status": "pending"},
        {"step": "Ejecutar validación técnica y decidir publicación.", "status": "pending"},
    ]
    return {
        "enabled": True,
        "mode": mode,
        "target": _truncate(question_text, 220),
        "area": str(detail.get("area") or ""),
        "candidate_files": [str(item) for item in (detail.get("candidate_files") or []) if str(item or "").strip()][:8],
        "suggested_checks": [str(item) for item in (detail.get("suggested_checks") or []) if str(item or "").strip()][:4],
        "requested_tools": requested_tools[:8],
        "objectives": objectives[:4],
        "constraints": constraints[:5],
        "change_plan": change_plan,
        "authorized_for_code": bool(auth.get("allowed")),
        "authorized_for_publish": bool(publish_auth.get("allowed")),
        "catalog_candidates": [row for row in (_catalog_candidates_for_question(question) or []) if isinstance(row, dict)][:3],
    }


def _file_change_role(path: str, question: str) -> dict:
    lower_path = str(path or "").lower()
    lower_question = str(question or "").lower()
    if lower_path.endswith(".html"):
        return {
            "change_type": "template",
            "objective": "Ajustar markup, hooks de UI o estructura de pantalla.",
            "risk": "medium",
        }
    if lower_path.endswith(".js"):
        objective = "Refinar comportamiento cliente, listeners y navegación."
        if "3d" in lower_question or "pitch3d" in lower_question or "estadio" in lower_question:
            objective = "Corregir la lógica cliente del flujo 3D y sus triggers."
        return {
            "change_type": "frontend_logic",
            "objective": objective,
            "risk": "medium",
        }
    if lower_path.endswith(".py"):
        return {
            "change_type": "backend_logic",
            "objective": "Modificar routing, contexto o lógica de servidor.",
            "risk": "high",
        }
    return {
        "change_type": "code",
        "objective": "Aplicar el cambio técnico solicitado en este archivo.",
        "risk": "medium",
    }


def _build_change_blueprint(question: str, code_operator_mode: dict, *, planner: dict, technical_execution=None) -> dict:
    if not isinstance(code_operator_mode, dict) or not code_operator_mode.get("enabled"):
        return {}
    files = [str(item) for item in (code_operator_mode.get("candidate_files") or []) if str(item or "").strip()]
    catalog_candidates = [row for row in (code_operator_mode.get("catalog_candidates") or []) if isinstance(row, dict)]
    requested_tools = [str(item) for item in (code_operator_mode.get("requested_tools") or []) if str(item or "").strip()]
    patch_drafts = []
    for candidate in catalog_candidates[:2]:
        item = CODE_INTERVENTION_CATALOG.get(str(candidate.get("key") or "").strip()) or {}
        for patch in (item.get("patches") or [])[:3]:
            if not isinstance(patch, dict):
                continue
            patch_drafts.append({
                "path": str(patch.get("path") or ""),
                "strategy": "exact_text_patch",
                "search": _truncate(str(patch.get("search") or ""), 180),
                "replace_preview": _truncate(str(patch.get("replace") or ""), 180),
            })
    file_changes = []
    for path in files[:6]:
        role = _file_change_role(path, question)
        file_changes.append({
            "path": path,
            "change_type": role["change_type"],
            "objective": role["objective"],
            "risk": role["risk"],
        })
    validation_plan = []
    if "inspect_repo_status" in requested_tools:
        validation_plan.append("Revisar diff y archivos modificados en el repositorio.")
    if "run_operator_validation" in requested_tools:
        validation_plan.append("Ejecutar `manage.py check` y validación técnica del operador.")
    if "inspect_recent_errors" in requested_tools:
        validation_plan.append("Cruzar el cambio con errores recientes antes de publicar.")
    if not validation_plan:
        validation_plan.append("Ejecutar validación técnica mínima antes de publicar.")
    publish_notes = []
    if bool(code_operator_mode.get("authorized_for_publish")):
        publish_notes.append("Si la validación termina correcta, preparar commit y push con mensaje técnico claro.")
    else:
        publish_notes.append("El cambio debe quedarse en revisión hasta que un operador autorizado publique.")
    if isinstance(technical_execution, dict) and technical_execution.get("completed_phases"):
        publish_notes.append(f"Fases ya completadas: {', '.join(technical_execution.get('completed_phases')[:4])}.")
    return {
        "enabled": True,
        "mode": str(code_operator_mode.get("mode") or ""),
        "target": str(code_operator_mode.get("target") or ""),
        "file_changes": file_changes,
        "patch_drafts": patch_drafts,
        "validation_plan": validation_plan[:4],
        "publish_notes": publish_notes[:3],
        "requested_tools": requested_tools[:8],
    }


def _build_autofix_runner(question: str, *, technical_operation=None, technical_execution=None, change_blueprint=None) -> dict:
    technical_operation = technical_operation if isinstance(technical_operation, dict) else {}
    technical_execution = technical_execution if isinstance(technical_execution, dict) else {}
    change_blueprint = change_blueprint if isinstance(change_blueprint, dict) else {}
    if str(technical_operation.get("kind") or "") != "technical_operation":
        return {}
    applied = [row for row in (technical_execution.get("applied_interventions") or []) if isinstance(row, dict)]
    catalog_candidates = [row for row in (technical_operation.get("catalog_candidates") or []) if isinstance(row, dict)]
    pending_patches = [row for row in (change_blueprint.get("patch_drafts") or []) if isinstance(row, dict)]
    executable = bool(technical_operation.get("authorized_for_code")) and (
        bool(applied) or any(bool(row.get("auto_apply")) for row in catalog_candidates)
    )
    next_actions = []
    if executable and not applied and pending_patches:
        next_actions.append("Aplicar parche catalogado o intervención exacta sobre el archivo objetivo.")
    if technical_execution.get("ok"):
        next_actions.append("Revisar diff final y decidir si el cambio queda listo para publicar.")
    elif technical_execution.get("completed_phases"):
        next_actions.append("Resolver la fase pendiente antes de ampliar la intervención.")
    else:
        next_actions.append("Completar triage y validación antes de tocar código.")
    return {
        "active": True,
        "target": _truncate(question, 220),
        "executable": executable,
        "applied_catalog_fixes": [
            {
                "key": str(row.get("candidate_key") or ""),
                "title": str(row.get("title") or row.get("candidate_key") or ""),
                "ok": bool(row.get("ok")),
                "applied_count": _safe_int(row.get("applied_count"), 0),
            }
            for row in applied[:3]
        ],
        "pending_patch_drafts": pending_patches[:4],
        "validation_plan": [str(item) for item in (change_blueprint.get("validation_plan") or []) if str(item or "").strip()][:4],
        "publish_ready": bool(technical_execution.get("publish_ready")),
        "next_actions": next_actions[:3],
    }


def _build_technical_operation(assistant_action: dict, planner: dict, *, page_context=None) -> dict:
    if str((assistant_action or {}).get("kind") or "") != "code_intervention_request":
        return {}
    payload = assistant_action.get("payload") if isinstance(assistant_action.get("payload"), dict) else {}
    files = [str(item) for item in (assistant_action.get("candidate_files") or payload.get("candidate_files") or []) if str(item or "").strip()]
    checks = [str(item) for item in (assistant_action.get("suggested_checks") or payload.get("suggested_checks") or []) if str(item or "").strip()]
    catalog_candidates = [row for row in (assistant_action.get("catalog_candidates") or payload.get("catalog_candidates") or []) if isinstance(row, dict)]
    requested_tools = [str(item) for item in (planner.get("requested_tools") or []) if str(item or "").strip()]
    auth = assistant_action.get("authorization") if isinstance(assistant_action.get("authorization"), dict) else _authorize_guard_action("repair_code", page_context=page_context)
    publish_auth = assistant_action.get("publish_authorization") if isinstance(assistant_action.get("publish_authorization"), dict) else _authorize_guard_action("publish_changes", page_context=page_context)
    phases = [
        {
            "key": "triage",
            "label": "Triage técnico",
            "objective": "Aislar la causa probable y confirmar el área afectada.",
            "tools": ["check_status", "inspect_recent_errors"],
        },
        {
            "key": "inspect_repo",
            "label": "Inspección de repositorio",
            "objective": "Revisar diff, riesgos y archivos implicados.",
            "tools": ["inspect_repo_status"],
        },
        {
            "key": "validate",
            "label": "Validación previa",
            "objective": "Ejecutar check/tests antes y después de tocar código.",
            "tools": ["run_operator_validation"],
        },
        {
            "key": "repair",
            "label": "Intervención de código",
            "objective": "Aplicar el ajuste necesario en los ficheros candidatos.",
            "tools": ["auto_fix"],
        },
        {
            "key": "publish",
            "label": "Publicación",
            "objective": "Crear commit y push cuando la validación sea correcta.",
            "tools": ["git_commit", "git_push"],
        },
    ]
    next_step = "Esperar autorización de código."
    if auth.get("allowed"):
        next_step = "Inspeccionar el repositorio y validar el área afectada."
    if planner.get("confirm_required"):
        next_step = "Esperar confirmación antes de publicar cambios sensibles."
    return {
        "kind": "technical_operation",
        "active": True,
        "target": str(assistant_action.get("target") or payload.get("target") or ""),
        "area": str(assistant_action.get("target_area") or payload.get("area") or ""),
        "candidate_files": files[:6],
        "suggested_checks": checks[:4],
        "catalog_candidates": catalog_candidates[:3],
        "requested_tools": requested_tools[:8],
        "phases": phases,
        "next_step": next_step,
        "authorized_for_code": bool(auth.get("allowed")),
        "authorized_for_publish": bool(publish_auth.get("allowed")),
        "publish_requires_confirmation": bool(planner.get("confirm_required")),
    }


def _execute_controlled_technical_operation(
    operation: dict,
    *,
    executed_tools=None,
    workspace=None,
    question: str = "",
    smoke_verbosity: int = 1,
) -> dict:
    if str((operation or {}).get("kind") or "") != "technical_operation":
        return {}
    if not bool(operation.get("authorized_for_code")):
        return {
            "kind": "technical_operation_execution",
            "executed": False,
            "ok": False,
            "status": "blocked",
            "reason": "not_authorized_for_code",
            "new_executions": [],
            "executions": [row for row in (executed_tools or []) if isinstance(row, dict)],
            "completed_phases": [],
            "next_step": "Esperar a un operador autorizado para intervenir sobre código.",
            "publish_ready": False,
        }
    safe_tools = ["check_status", "inspect_repo_status", "run_operator_validation"]
    if re.search(r"\b(error|errores|log|logs|traceback)\b", str(question or "").lower()):
        safe_tools.append("inspect_recent_errors")
    existing = [row for row in (executed_tools or []) if isinstance(row, dict)]
    existing_keys = {str(row.get("tool") or "") for row in existing}
    missing = [tool for tool in safe_tools if tool not in existing_keys]
    new_executions = _execute_tools(missing, smoke_verbosity=smoke_verbosity, workspace=workspace, question=question) if missing else []
    combined = existing + new_executions
    tool_ok = {
        str(row.get("tool") or ""): bool(row.get("ok"))
        for row in combined
        if isinstance(row, dict)
    }
    applied_interventions = []
    completed_phases = []
    if tool_ok.get("check_status"):
        completed_phases.append("triage")
    if tool_ok.get("inspect_repo_status"):
        completed_phases.append("inspect_repo")
    if tool_ok.get("run_operator_validation"):
        completed_phases.append("validate")
    repo_ok = bool(tool_ok.get("inspect_repo_status"))
    validate_ok = bool(tool_ok.get("run_operator_validation"))
    catalog_candidates = [row for row in (operation.get("catalog_candidates") or []) if isinstance(row, dict)]
    auto_apply_candidate = next((
        row for row in catalog_candidates
        if bool(row.get("auto_apply")) or bool((CODE_INTERVENTION_CATALOG.get(str(row.get("key") or "").strip()) or {}).get("auto_apply"))
    ), None)
    if validate_ok and auto_apply_candidate:
        catalog_result = _execute_catalog_code_intervention(str(auto_apply_candidate.get("key") or ""))
        applied_interventions.append(catalog_result)
        if catalog_result.get("ok"):
            repair_execution = _serialize_execution(
                f"catalog_fix:{catalog_result.get('candidate_key')}",
                {
                    "ok": True,
                    "action": "catalog_code_intervention",
                    "detail": catalog_result,
                },
            )
            repair_execution["kind"] = "repair"
            combined.append(repair_execution)
            post_validation = _serialize_execution("run_operator_validation", _run_operator_validation())
            combined.append(post_validation)
            tool_ok["run_operator_validation"] = bool(post_validation.get("ok"))
            validate_ok = bool(post_validation.get("ok"))
            completed_phases.append("repair")
    publish_ready = bool(repo_ok and validate_ok and operation.get("authorized_for_publish"))
    next_step = "Revisar el repositorio y la validación antes de tocar código."
    if validate_ok:
        next_step = "La operación está lista para intervención manual de código y, si procede, para preparar publicación."
    if publish_ready and bool(operation.get("publish_requires_confirmation")):
        next_step = "La validación está correcta; falta confirmación para commit y push."
    if any(bool(row.get("ok")) for row in applied_interventions):
        next_step = "Se ha aplicado un fix catalogado y la validación posterior ha terminado."
    if any(not bool(row.get("ok")) for row in new_executions):
        next_step = "Resolver el fallo detectado en triage o validación antes de continuar."
    status = "completed" if validate_ok else ("running" if (repo_ok or tool_ok.get("check_status")) else "blocked")
    return {
        "kind": "technical_operation_execution",
        "executed": bool(new_executions),
        "ok": bool(repo_ok and validate_ok),
        "status": status,
        "new_executions": new_executions,
        "executions": combined,
        "completed_phases": completed_phases,
        "applied_interventions": applied_interventions,
        "next_step": next_step,
        "publish_ready": publish_ready,
    }


def _resolve_assisted_action(question: str, *, workspace=None, page_context=None) -> dict:
    intent = _infer_intent(question)
    task = _build_task_profile(question, intent=intent, page_context=page_context)
    if intent in {"repair", "feature_request"} and str(task.get("scope") or "") == "code":
        return _build_code_intervention_request(question, workspace=workspace, page_context=page_context)
    if str(task.get("kind") or "") == "navigate":
        return _execute_navigation_action(question, page_context=page_context)
    if intent == "guide_user":
        return _execute_guidance_action(question, page_context=page_context)
    if intent == "create_player":
        return _execute_create_player_action(question, workspace=workspace, page_context=page_context)
    if intent == "create_session":
        return _execute_create_session_action(question, workspace=workspace, page_context=page_context)
    if intent == "create_task":
        return _execute_create_task_action(question, workspace=workspace, page_context=page_context)
    return {}


def _infer_intent(question: str) -> str:
    text = str(question or "").strip().lower()
    if re.search(r"\b(abre|abrir|ll[ée]vame|llevame|ve a|ir a|quiero ir|quiero abrir|quiero ver)\b", text):
        return "navigate_module"
    if re.search(r"\b(auto[\s-]?fix|arregl\w*|corrig\w*|repar\w*|solucion\w*)\b", text):
        return "repair"
    if re.search(r"\b(añade|agrega|implementa|crea|construye|desarrolla|modifica|extiende)\b", text) and re.search(r"\b(funcionalidad|feature|modulo|módulo|flujo|pantalla|widget|sistema|codigo|código)\b", text):
        return "feature_request"
    if re.search(r"\b(crea|crear|genera|prepara|añade|agrega)\b.*\b(tarea|task|ejercicio)\b", text):
        return "create_task"
    if re.search(r"\b(crea|crear|programa|planifica|prepara|monta)\b.*\b(sesion|sesión|entreno|entrenamiento)\b", text):
        return "create_session"
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


def _operator_blueprint(question: str, *, planner: dict, page_context=None, response=None) -> dict:
    task = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    if str(task.get("scope") or "") != "code":
        return {}
    requested_tools = [str(item) for item in (planner.get("requested_tools") or []) if str(item or "").strip()]
    executed_tools = [row for row in ((response or {}).get("executions") or []) if isinstance(row, dict)]
    auth = _authorize_guard_action("repair_code", page_context=page_context)
    publish_auth = _authorize_guard_action("publish_changes", page_context=page_context)
    phases = [
        {
            "key": "inspect",
            "label": "Inspección técnica",
            "done": "inspect_repo_status" in requested_tools or any(str(row.get("tool") or "") == "inspect_repo_status" for row in executed_tools),
        },
        {
            "key": "validate",
            "label": "Validación",
            "done": "run_operator_validation" in requested_tools or any(str(row.get("tool") or "") == "run_operator_validation" for row in executed_tools),
        },
        {
            "key": "repair",
            "label": "Intervención de código",
            "done": any(str(row.get("kind") or "") == "repair" and bool(row.get("ok")) for row in executed_tools),
        },
        {
            "key": "publish",
            "label": "Publicación",
            "done": any(str(row.get("tool") or "") == "git_push" and bool(row.get("ok")) for row in executed_tools),
        },
    ]
    next_step = "Diagnosticar el repositorio antes de tocar código."
    if not auth.get("allowed"):
        next_step = "Esperar a un usuario operador autorizado para intervenir sobre código."
    elif planner.get("confirm_required"):
        next_step = "Esperar confirmación antes de ejecutar cambios sensibles."
    elif "run_operator_validation" in requested_tools:
        next_step = "Completar validación y revisar el diff antes de publicar."
    elif "inspect_repo_status" in requested_tools:
        next_step = "Revisar estado del repositorio y decidir si toca validar o reparar."
    return {
        "active": True,
        "question": _truncate(question, 200),
        "target_summary": str(task.get("target_summary") or _truncate(question, 200)),
        "intervention_requested": str(task.get("kind") or "") in {"repair", "code_workflow", "publish"},
        "authorized_for_code": bool(auth.get("allowed")),
        "authorized_for_publish": bool(publish_auth.get("allowed")),
        "needs_confirmation": bool(planner.get("confirm_required")),
        "runbook_key": str((planner.get("runbook") or {}).get("key") or ""),
        "phases": phases,
        "publish_ready": bool(publish_auth.get("allowed")) and any(phase.get("key") == "validate" and phase.get("done") for phase in phases) and not bool(planner.get("confirm_required")),
        "next_step": next_step,
    }


def _plan_tools(question: str, *, run_smoke: bool, auto_fix: bool, maintenance_action: str, autonomy_mode: str, page_context=None) -> dict:
    intent = _infer_intent(question)
    task = _build_task_profile(question, intent=intent, maintenance_action=maintenance_action, page_context=page_context)
    requested_tools = []
    steps = [{"step": "Diagnosticar estado base", "done": True}]
    question_lower = str(question or "").lower()
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
        if re.search(r"\b(test|tests|check|valida|validacion|validación)\b", str(question or "").lower()):
            requested_tools.append("run_operator_validation")
    elif intent == "operator_validate":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation"])
    elif intent == "feature_request":
        requested_tools.extend(["inspect_repo_status", "run_operator_validation"])
        if re.search(r"\b(error|errores|traceback|logs?)\b", question_lower):
            requested_tools.append("inspect_recent_errors")
    elif auto_fix:
        requested_tools.append("auto_fix")
    elif run_smoke:
        requested_tools.append("run_smoke")
    elif intent == "maintenance_previews":
        requested_tools.append("regenerate_task_previews")
    elif intent == "maintenance_reindex":
        requested_tools.append("ai_trainer_reindex")
    elif intent == "repair":
        if str(task.get("scope") or "") == "code":
            requested_tools.extend(["inspect_repo_status", "run_operator_validation", "auto_fix"])
            if re.search(r"\b(error|errores|log|logs|traceback)\b", question_lower):
                requested_tools.append("inspect_recent_errors")
        else:
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
    if str(task.get("kind") or "") == "code_workflow":
        if "inspect_repo_status" not in requested_tools:
            requested_tools.insert(0, "inspect_repo_status")
        if re.search(r"\b(test|tests|check|valida|validacion|validación)\b", question_lower) and "run_operator_validation" not in requested_tools:
            requested_tools.append("run_operator_validation")
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


def _adapt_response_to_live_workflow(response: dict, *, page_context=None) -> dict:
    response = dict(response or {})
    intelligence_os = response.get("intelligence_os") if isinstance(response.get("intelligence_os"), dict) else {}
    layers = intelligence_os.get("layers") if isinstance(intelligence_os.get("layers"), dict) else {}
    workflow = layers.get("live_workflow") if isinstance(layers.get("live_workflow"), dict) else {}
    if not workflow:
        return response
    selected_session = workflow.get("selected_session") if isinstance(workflow.get("selected_session"), dict) else {}
    selected_task = workflow.get("selected_task") if isinstance(workflow.get("selected_task"), dict) else {}
    selected_microcycle = workflow.get("selected_microcycle") if isinstance(workflow.get("selected_microcycle"), dict) else {}
    active_match = workflow.get("active_match") if isinstance(workflow.get("active_match"), dict) else {}
    page_tab = str(workflow.get("page_tab") or "")[:64]
    highlights = list(response.get("highlights") or [])
    ui_actions = list(response.get("ui_actions") or [])
    message = str(response.get("message") or "")

    if selected_session.get("id"):
        highlights.append(f"Sesión activa: {selected_session.get('focus') or 'sesión'}")
        ui_actions.insert(0, {
            "type": "prompt",
            "label": "Analizar sesión abierta",
            "prompt": f"Analiza la sesión abierta {selected_session.get('focus') or ''} y dime el siguiente ajuste útil.",
            "reason": "Trabajar sobre la sesión que el usuario tiene en foco.",
        })
        if "sesión" not in message.lower() and "session" not in message.lower():
            message += f" Estoy situado sobre la sesión {selected_session.get('focus') or ''}."
    if selected_task.get("id"):
        highlights.append(f"Tarea activa: {selected_task.get('title') or 'tarea'}")
        ui_actions.insert(0, {
            "type": "prompt",
            "label": "Revisar tarea abierta",
            "prompt": f"Revisa la tarea abierta {selected_task.get('title') or ''} y propón mejora o corrección.",
            "reason": "Trabajar sobre la tarea que está abierta ahora mismo.",
        })
    if selected_microcycle.get("id"):
        highlights.append(f"Microciclo activo: {selected_microcycle.get('title') or 'microciclo'}")
    if active_match.get("id"):
        rival = str(active_match.get("away_team") or active_match.get("home_team") or "").strip()
        highlights.append(f"Partido activo: {rival or active_match.get('id')}")
        ui_actions.insert(0, {
            "type": "prompt",
            "label": "Trabajar sobre partido",
            "prompt": "Explícame el partido activo, el contexto rival y la siguiente decisión útil.",
            "reason": "Adaptar la ayuda al partido actualmente seleccionado.",
        })
    if page_tab:
        highlights.append(f"Tab activa: {page_tab}")

    response["message"] = _truncate(message.strip(), 1800)
    response["highlights"] = highlights[:10]
    response["ui_actions"] = ui_actions[:6]
    return response


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
        "capabilities": {},
        "operator_plan": {},
        "autofix_runner": {},
        "silent_operator": {},
        "operator_profile": {},
        "intelligence_os": {},
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
        "capabilities": fallback.get("capabilities") or {},
        "operator_plan": fallback.get("operator_plan") or {},
        "autofix_runner": fallback.get("autofix_runner") or {},
        "silent_operator": fallback.get("silent_operator") or {},
        "operator_profile": fallback.get("operator_profile") or {},
        "intelligence_os": fallback.get("intelligence_os") or {},
    })
    return merged


def _build_silent_operator_state(workspace, *, response=None, actor_id=None) -> dict:
    queue_rows = _load_task_queue(workspace)
    proactive = _load_proactive_state(workspace)
    scheduled = _scheduled_guard_state(workspace)
    profile = _load_operator_profile(workspace, actor_id=actor_id)
    queue_counts = _task_state_counts(queue_rows)
    now_ts = int(time.time())
    last_started = _safe_int(scheduled.get("last_started_ts"), 0)
    elapsed = max(0, now_ts - last_started) if last_started else 0
    next_cycle_in = max(0, int(SCHEDULED_GUARD_INTERVAL_SECONDS) - elapsed) if last_started else 0
    suggested = []
    if queue_counts.get("blocked", 0):
        suggested.append("Revisar tareas bloqueadas del operador silencioso.")
    if queue_counts.get("pending", 0):
        suggested.append("Procesar backlog silencioso pendiente.")
    if not suggested:
        suggested.append("Mantener inspección continua y preparar la siguiente mejora preventiva.")
    top_intent = ""
    recurring = [row for row in (profile.get("recurring_intents") or []) if isinstance(row, dict)]
    if recurring:
        top_intent = str(recurring[0].get("intent") or "")[:64]
    return {
        "enabled": True,
        "continuous_enabled": True,
        "queue_counts": queue_counts,
        "last_cycle_at": str(proactive.get("last_cycle_at") or scheduled.get("last_finished_at") or "")[:64],
        "last_detection_count": _safe_int(proactive.get("last_detection_count"), 0),
        "last_improvement_count": _safe_int(proactive.get("last_improvement_count"), 0),
        "next_cycle_in_seconds": next_cycle_in,
        "preferred_route": str(profile.get("preferred_route_label") or "")[:120],
        "top_intent": top_intent,
        "suggested_actions": suggested[:3],
        "publish_ready": bool(((response or {}).get("technical_operation_execution") or {}).get("publish_ready")),
    }


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
    code_operator_mode = _build_code_operator_mode(question, planner, page_context=page_context)
    technical_operation = _build_technical_operation(assistant_action if isinstance(assistant_action, dict) else {}, planner, page_context=page_context)
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
    technical_execution = _execute_controlled_technical_operation(
        technical_operation if isinstance(technical_operation, dict) else {},
        executed_tools=executed_tools,
        workspace=workspace,
        question=question,
        smoke_verbosity=smoke_verbosity,
    )
    if isinstance(technical_execution, dict) and technical_execution.get("new_executions"):
        executed_tools = [row for row in (technical_execution.get("executions") or []) if isinstance(row, dict)]
    change_blueprint = _build_change_blueprint(
        question,
        code_operator_mode if isinstance(code_operator_mode, dict) else {},
        planner=planner,
        technical_execution=technical_execution if isinstance(technical_execution, dict) else {},
    )
    autofix_runner = _build_autofix_runner(
        question,
        technical_operation=technical_operation if isinstance(technical_operation, dict) else {},
        technical_execution=technical_execution if isinstance(technical_execution, dict) else {},
        change_blueprint=change_blueprint if isinstance(change_blueprint, dict) else {},
    )
    queue_event = {}
    task_meta = planner.get("task") if isinstance(planner.get("task"), dict) else {}
    runbook_meta = planner.get("runbook") if isinstance(planner.get("runbook"), dict) else {}
    queue_title = str(task_meta.get("title") or "").strip() or _truncate(question, 120)
    if assistant_action and workspace:
        queue_status = "completed" if assistant_action.get("success") else ("blocked" if assistant_action.get("permission_required") else "pending")
        queue_event = _record_task_queue_event(
            workspace,
            title=queue_title,
            summary=str(assistant_action.get("message") or "Acción asistida manual.")[:280],
            task_kind=str(task_meta.get("kind") or assistant_action.get("kind") or "execute"),
            runbook=str(runbook_meta.get("key") or task_meta.get("runbook_key") or "user_execution"),
            tools=list(planner.get("requested_tools") or []),
            source="manual_assistant",
            status=queue_status,
            question=question,
            result_summary=str(assistant_action.get("message") or "")[:280],
            executions=[],
            metadata={"assistant_action": assistant_action, "technical_operation": technical_operation, "technical_execution": technical_execution, "code_operator_mode": code_operator_mode, "change_blueprint": change_blueprint} if technical_operation else {"assistant_action": assistant_action, "code_operator_mode": code_operator_mode, "change_blueprint": change_blueprint},
        )
    elif planner.get("requested_tools") and workspace:
        queue_status = "pending" if planner.get("confirm_required") else ("completed" if all(bool(row.get("ok")) for row in executed_tools or []) else "blocked")
        queue_event = _record_task_queue_event(
            workspace,
            title=queue_title,
            summary=f"Runbook {str(runbook_meta.get('title') or runbook_meta.get('key') or 'guard')} para: {_truncate(question, 140)}",
            task_kind=str(task_meta.get("kind") or "diagnose"),
            runbook=str(runbook_meta.get("key") or task_meta.get("runbook_key") or "silent_diagnostics"),
            tools=list(planner.get("requested_tools") or []),
            source="manual_runbook",
            status=queue_status,
            question=question,
            result_summary="Acciones completadas." if queue_status == "completed" else ("Pendiente de confirmación." if queue_status == "pending" else "Una o más acciones fallaron."),
            executions=executed_tools,
        )
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
    fallback["capabilities"] = _capability_snapshot(page_context=page_context)
    fallback["operator_plan"] = _operator_blueprint(question, planner=planner, page_context=page_context, response=fallback)
    fallback["code_operator_mode"] = code_operator_mode if isinstance(code_operator_mode, dict) else {}
    fallback["change_blueprint"] = change_blueprint if isinstance(change_blueprint, dict) else {}
    fallback["technical_operation"] = technical_operation if isinstance(technical_operation, dict) else {}
    fallback["technical_operation_execution"] = technical_execution if isinstance(technical_execution, dict) else {}
    fallback["autofix_runner"] = autofix_runner if isinstance(autofix_runner, dict) else {}
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
        if assistant_action.get("kind") == "code_intervention_request":
            target_area = str(assistant_action.get("target_area") or "").strip()
            candidate_files = [str(item) for item in (assistant_action.get("candidate_files") or []) if str(item or "").strip()]
            suggested_checks = [str(item) for item in (assistant_action.get("suggested_checks") or []) if str(item or "").strip()]
            catalog_candidates = [row for row in (assistant_action.get("catalog_candidates") or []) if isinstance(row, dict)]
            if target_area:
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Intervención técnica: {target_area}"]
            if candidate_files:
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Ficheros candidatos: {', '.join(candidate_files[:3])}"]
            if catalog_candidates:
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Fix catalogado candidato: {catalog_candidates[0].get('title') or catalog_candidates[0].get('key')}"]
            if suggested_checks:
                fallback["actions"] = [{
                    "type": "prompt",
                    "label": "Inspección técnica guiada",
                    "prompt": f"Revisa {', '.join(candidate_files[:2]) or 'el área afectada'} y valida: {suggested_checks[0]}",
                    "reason": "Arrancar una intervención concreta sobre código.",
                }, {
                    "type": "prompt",
                    "label": "Preparar publicación",
                    "prompt": "Cuando el cambio esté validado, prepara commit y push con un mensaje técnico claro.",
                    "reason": "Cerrar el flujo técnico hasta publicación.",
                }] + (fallback.get("actions") or [])
            if isinstance(technical_execution, dict) and technical_execution.get("completed_phases"):
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Fases completadas: {', '.join(technical_execution.get('completed_phases')[:4])}"]
            applied_interventions = [row for row in (technical_execution.get("applied_interventions") or []) if isinstance(row, dict)] if isinstance(technical_execution, dict) else []
            if any(bool(row.get("ok")) for row in applied_interventions):
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Fix aplicado: {applied_interventions[0].get('title') or applied_interventions[0].get('candidate_key')}"]
        if isinstance(code_operator_mode, dict) and code_operator_mode.get("enabled"):
            fallback["highlights"] = (fallback.get("highlights") or []) + [f"Modo operador: {code_operator_mode.get('mode')}"]
        if isinstance(change_blueprint, dict) and change_blueprint.get("file_changes"):
            fallback["highlights"] = (fallback.get("highlights") or []) + [f"Blueprint de cambio: {len(change_blueprint.get('file_changes') or [])} archivos objetivo"]
        if assistant_action.get("navigate_to") and isinstance(assistant_action.get("navigate_to"), dict):
            route = assistant_action.get("navigate_to") or {}
            fallback["ui_actions"] = [{
                "type": "navigate",
                "label": f"Abrir {route.get('label') or 'destino'}",
                "url": str(route.get("url") or ""),
                "reason": "Navegación resuelta por Ollana.",
            }] + (fallback.get("ui_actions") or [])
        payload = assistant_action.get("payload") if isinstance(assistant_action.get("payload"), dict) else {}
        if payload:
            collected = []
            for key in ("name", "number", "position", "dominant_foot", "title", "repository", "duration_minutes"):
                value = payload.get(key)
                if value not in ("", None):
                    collected.append(f"{key}:{value}")
            if collected:
                fallback["highlights"] = (fallback.get("highlights") or []) + [f"Datos capturados: {', '.join(collected[:4])}"]
        if assistant_action.get("missing_fields"):
            fallback["actions"] = [{
                "label": "Completar datos para ejecutar",
                "reason": "Faltan campos mínimos para ejecutar la petición.",
            }] + (fallback.get("actions") or [])
        if queue_event:
            fallback["highlights"] = (fallback.get("highlights") or []) + [f"Cola: {queue_event.get('status') or 'registrada'}"]
    operator_profile = _load_operator_profile(workspace, actor_id=actor_id)
    fallback["operator_profile"] = operator_profile
    fallback["silent_operator"] = _build_silent_operator_state(workspace, response=fallback, actor_id=actor_id)
    fallback["intelligence_os"] = _build_intelligence_os_snapshot(
        question,
        workspace=workspace,
        page_context=page_context,
        planner=planner,
        assistant_action=assistant_action if isinstance(assistant_action, dict) else {},
        technical_operation=technical_operation if isinstance(technical_operation, dict) else {},
        technical_execution=technical_execution if isinstance(technical_execution, dict) else {},
        code_operator_mode=code_operator_mode if isinstance(code_operator_mode, dict) else {},
        change_blueprint=change_blueprint if isinstance(change_blueprint, dict) else {},
        autofix_runner=autofix_runner if isinstance(autofix_runner, dict) else {},
        operator_profile=operator_profile,
        silent_operator=fallback.get("silent_operator") if isinstance(fallback.get("silent_operator"), dict) else {},
        improvement_proposals=fallback.get("improvement_proposals") if isinstance(fallback.get("improvement_proposals"), list) else [],
        snapshot_diff=fallback.get("snapshot_diff") if isinstance(fallback.get("snapshot_diff"), dict) else {},
    )
    fallback = _adapt_response_to_live_workflow(fallback, page_context=page_context)
    fallback["runbook"] = _runbook_execution_summary(
        fallback.get("runbook") if isinstance(fallback.get("runbook"), dict) else {},
        executed_tools=executed_tools,
        assistant_action=assistant_action if isinstance(assistant_action, dict) else {},
        status=str(fallback.get("status") or ""),
        needs_confirmation=bool(fallback.get("needs_confirmation")),
    )
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
    response["capabilities"] = response.get("capabilities") or _capability_snapshot(page_context=page_context)
    response["operator_plan"] = _operator_blueprint(question, planner=planner, page_context=page_context, response=response)
    response["code_operator_mode"] = response.get("code_operator_mode") or code_operator_mode
    response["change_blueprint"] = response.get("change_blueprint") or change_blueprint
    response["technical_operation"] = response.get("technical_operation") or technical_operation
    response["technical_operation_execution"] = response.get("technical_operation_execution") or technical_execution
    response["autofix_runner"] = response.get("autofix_runner") or autofix_runner
    response["memory_hint"] = _truncate(memory.get("summary"), 220)
    response["runbook"] = _runbook_execution_summary(
        response.get("runbook") if isinstance(response.get("runbook"), dict) else {},
        executed_tools=executed_tools,
        assistant_action=response.get("assistant_action") if isinstance(response.get("assistant_action"), dict) else {},
        status=str(response.get("status") or ""),
        needs_confirmation=bool(response.get("needs_confirmation")),
    )
    if snapshot_diff.get("regressions"):
        response["highlights"] = (response.get("highlights") or []) + [f"Regresión: {item}" for item in snapshot_diff.get("regressions", [])[:2]]
    elif snapshot_diff.get("improvements"):
        response["highlights"] = (response.get("highlights") or []) + [f"Mejora: {item}" for item in snapshot_diff.get("improvements", [])[:2]]
    _store_operator_profile(workspace, actor_id=actor_id, planner=planner, assistant_action=response.get("assistant_action"), question=question, page_context=page_context)
    response["operator_profile"] = _load_operator_profile(workspace, actor_id=actor_id)
    response["silent_operator"] = _build_silent_operator_state(workspace, response=response, actor_id=actor_id)
    response["intelligence_os"] = _build_intelligence_os_snapshot(
        question,
        workspace=workspace,
        page_context=page_context,
        planner=planner,
        assistant_action=response.get("assistant_action") if isinstance(response.get("assistant_action"), dict) else {},
        technical_operation=response.get("technical_operation") if isinstance(response.get("technical_operation"), dict) else {},
        technical_execution=response.get("technical_operation_execution") if isinstance(response.get("technical_operation_execution"), dict) else {},
        code_operator_mode=response.get("code_operator_mode") if isinstance(response.get("code_operator_mode"), dict) else {},
        change_blueprint=response.get("change_blueprint") if isinstance(response.get("change_blueprint"), dict) else {},
        autofix_runner=response.get("autofix_runner") if isinstance(response.get("autofix_runner"), dict) else {},
        operator_profile=response.get("operator_profile") if isinstance(response.get("operator_profile"), dict) else {},
        silent_operator=response.get("silent_operator") if isinstance(response.get("silent_operator"), dict) else {},
        improvement_proposals=response.get("improvement_proposals") if isinstance(response.get("improvement_proposals"), list) else [],
        snapshot_diff=response.get("snapshot_diff") if isinstance(response.get("snapshot_diff"), dict) else {},
    )
    response = _adapt_response_to_live_workflow(response, page_context=page_context)
    if isinstance(response.get("code_operator_mode"), dict) and response.get("code_operator_mode", {}).get("enabled"):
        mode_label = f"Modo operador: {response.get('code_operator_mode', {}).get('mode')}"
        current_highlights = [str(item) for item in (response.get("highlights") or []) if str(item or "").strip()]
        if mode_label not in current_highlights:
            response["highlights"] = [mode_label] + current_highlights
    for issue in (report.get("issues") or [])[:6]:
        if not isinstance(issue, dict):
            continue
        _append_incident_ledger(workspace, {
            "created_at": _now_iso(),
            "issue_id": str(issue.get("id") or ""),
            "status": str(response.get("status") or ""),
            "runbook": str((response.get("runbook") or {}).get("key") or ""),
            "summary": str(issue.get("detail") or issue.get("message") or issue.get("id") or ""),
            "kind": "issue",
        })
    if assistant_action and assistant_action.get("success"):
        _append_incident_ledger(workspace, {
            "created_at": _now_iso(),
            "issue_id": str(assistant_action.get("kind") or "assistant_action"),
            "status": "resolved",
            "runbook": str((response.get("runbook") or {}).get("key") or ""),
            "summary": str(assistant_action.get("message") or ""),
            "kind": "assistant_action",
        })
    elif assistant_action and str(assistant_action.get("kind") or "") == "code_intervention_request":
        _append_incident_ledger(workspace, {
            "created_at": _now_iso(),
            "issue_id": "code_intervention_request",
            "status": "pending" if not assistant_action.get("permission_required") else "blocked",
            "runbook": str((response.get("runbook") or {}).get("key") or ""),
            "summary": str(assistant_action.get("message") or ""),
            "kind": "assistant_action",
        })
    for row in executed_tools:
        if not isinstance(row, dict) or not row.get("ok"):
            continue
        kind = str(row.get("kind") or "")
        if kind not in {"repair", "publish", "maintenance"}:
            continue
        _append_incident_ledger(workspace, {
            "created_at": _now_iso(),
            "issue_id": str(row.get("tool") or ""),
            "status": "resolved",
            "runbook": str((response.get("runbook") or {}).get("key") or ""),
            "summary": str(row.get("label") or row.get("tool") or ""),
            "kind": kind,
        })
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
