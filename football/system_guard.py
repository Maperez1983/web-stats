from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

from football.healthchecks import run_system_healthcheck
from football.local_llm import call_ollama_json, local_llm_config


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_status(path_str: str) -> dict:
    path = Path(settings.BASE_DIR) / path_str
    return {
        "path": str(path),
        "exists": path.exists(),
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
    }


def _run_management_smoke(command_name: str, *, verbosity: int = 1) -> dict:
    stdout = StringIO()
    stderr = StringIO()
    try:
        call_command(command_name, stdout=stdout, stderr=stderr, verbosity=verbosity)
        return {
            "ok": True,
            "command": command_name,
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }
    except SystemExit as exc:
        code = int(exc.code or 1) if str(exc.code or "").isdigit() else 1
        return {
            "ok": False,
            "command": command_name,
            "exit_code": code,
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }
    except Exception as exc:
        return {
            "ok": False,
            "command": command_name,
            "error": f"{exc.__class__.__name__}: {exc}",
            "stdout": stdout.getvalue()[-6000:],
            "stderr": stderr.getvalue()[-3000:],
        }


def collect_system_guard_evidence(*, run_smoke: bool = False, smoke_verbosity: int = 1) -> dict:
    health = run_system_healthcheck()
    inventory = _module_inventory()
    cfg = local_llm_config()
    evidence = {
        "environment": _environment_snapshot(),
        "healthcheck": health,
        "module_inventory": inventory,
        "local_llm": {
            "enabled": bool(cfg.get("enabled")),
            "provider": str(cfg.get("provider") or ""),
            "model": str(cfg.get("model") or ""),
            "base_url": str(cfg.get("base_url") or ""),
            "timeout": int(cfg.get("timeout") or 0),
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


def build_system_guard_prompt(evidence: dict) -> str:
    payload = json.dumps(evidence or {}, ensure_ascii=False, separators=(",", ":"))
    return (
        "Eres un revisor senior de fiabilidad para una plataforma SaaS de fútbol. "
        "No eres un asistente conversacional; actúas como una capa de control del sistema. "
        "Analiza SOLO la evidencia JSON aportada por el sistema. "
        "Debes detectar fallos actuales, riesgos probables y huecos de cobertura antes de que el usuario los sufra. "
        "No inventes endpoints ni checks no presentes en la evidencia. "
        "Devuelve SOLO JSON válido con estas claves exactas: "
        "overall_status:string, blockers:list, warnings:list, prevention_actions:list, watch_modules:list, summary:string. "
        "overall_status debe ser uno de: ok, watch, risk, fail. "
        "blockers/warnings/prevention_actions/watch_modules: máximo 6 elementos por lista. "
        "Cada prevention_action debe ser un objeto con {area, action, reason}. "
        "watch_modules debe listar módulos del sistema que merecen vigilancia prioritaria con {module, reason}. "
        "Sé directo, técnico y en español.\n\n"
        f"EVIDENCE_JSON={payload}"
    )


def run_system_guard(*, run_smoke: bool = False, smoke_verbosity: int = 1, run_llm: bool = True) -> dict:
    evidence = collect_system_guard_evidence(run_smoke=run_smoke, smoke_verbosity=smoke_verbosity)
    report = {
        "ok": bool(evidence.get("healthcheck", {}).get("ok")),
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
        build_system_guard_prompt(evidence),
        model=cfg.get("model"),
        base_url=cfg.get("base_url"),
        timeout=cfg.get("timeout"),
    )
    report["llm_review"]["available"] = isinstance(parsed, dict)
    report["llm_review"]["error"] = str(error or "")
    report["llm_review"]["review"] = parsed if isinstance(parsed, dict) else None
    return report
