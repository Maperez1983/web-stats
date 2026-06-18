from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
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


def _probe_ollama(cfg: dict) -> dict:
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
        }
    req = urllib.request.Request(f"{base_url}/api/tags", headers={"Content-Type": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(2, int(cfg.get("timeout") or 8))) as resp:
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
        }
    models = payload.get("models") if isinstance(payload, dict) else []
    names = []
    for item in models if isinstance(models, list) else []:
        if not isinstance(item, dict):
            continue
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
    ollama_probe = _probe_ollama(cfg)
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
            "probe": ollama_probe,
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
    issues: list[dict] = []
    health = evidence.get("healthcheck") if isinstance(evidence.get("healthcheck"), dict) else {}
    db = health.get("database") if isinstance(health.get("database"), dict) else {}
    if not db.get("ok"):
        issues.append(_issue(
            "database_unhealthy",
            severity="blocker",
            area="database",
            message="La base de datos no responde correctamente.",
            detail=db.get("detail"),
        ))
    for key, item in (health.get("paths") or {}).items():
        if not isinstance(item, dict) or item.get("ok"):
            continue
        path_value = str(item.get("detail") or item.get("path") or "")
        auto_key = f"create_path:{path_value}" if path_value else ""
        issues.append(_issue(
            f"path_missing_{key}",
            severity="warning",
            area="filesystem",
            message=f"Falta la ruta crítica {key}.",
            detail=path_value,
            autofix=bool(path_value),
            autofix_key=auto_key,
        ))
    for key, item in (health.get("dependencies") or {}).items():
        if not isinstance(item, dict) or item.get("ok"):
            continue
        issues.append(_issue(
            f"dependency_{key}",
            severity="warning",
            area="dependencies",
            message=f"La dependencia {key} no está operativa.",
            detail=item.get("detail"),
        ))
    for key, item in (evidence.get("module_inventory") or {}).items():
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "script" and not item.get("exists"):
            issues.append(_issue(
                f"missing_script_{key}",
                severity="warning",
                area="coverage",
                message=f"Falta el smoke script del módulo {key}.",
                detail=item.get("path"),
            ))
    llm = evidence.get("local_llm") if isinstance(evidence.get("local_llm"), dict) else {}
    probe = llm.get("probe") if isinstance(llm.get("probe"), dict) else {}
    if llm.get("enabled") and not probe.get("reachable"):
        issues.append(_issue(
            "ollama_unreachable",
            severity="warning",
            area="local_llm",
            message="Ollama está configurado pero no responde.",
            detail=probe.get("error"),
        ))
    elif llm.get("enabled") and probe.get("reachable") and not probe.get("model_present"):
        issues.append(_issue(
            "ollama_model_missing",
            severity="warning",
            area="local_llm",
            message="Ollama responde pero el modelo configurado no está cargado.",
            detail=probe.get("model"),
        ))
    smoke = evidence.get("smoke") if isinstance(evidence.get("smoke"), dict) else {}
    for key, item in (smoke.get("results") or {}).items():
        if not isinstance(item, dict) or item.get("ok"):
            continue
        issues.append(_issue(
            f"smoke_failed_{key}",
            severity="blocker",
            area="smoke",
            message=f"Ha fallado el smoke {key}.",
            detail=item.get("error") or item.get("exit_code") or item.get("stderr") or item.get("stdout"),
        ))
    return issues


def _autofix_create_path(target_path: str) -> dict:
    path = Path(str(target_path or "").strip())
    if not str(path):
        return {"ok": False, "error": "empty_path"}
    try:
        path.mkdir(parents=True, exist_ok=True)
        return {"ok": path.exists(), "path": str(path)}
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": f"{exc.__class__.__name__}: {exc}"}


def _apply_autofix(issue: dict) -> dict:
    autofix_key = str(issue.get("autofix_key") or "").strip()
    if not autofix_key:
        return {"ok": False, "issue_id": issue.get("id"), "error": "missing_autofix_key"}
    if autofix_key.startswith("create_path:"):
        target = autofix_key.split(":", 1)[1]
        result = _autofix_create_path(target)
        result["issue_id"] = issue.get("id")
        result["action"] = "create_path"
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
        if result.get("ok"):
            applied.append(result)
        else:
            skipped.append(result)
    return {"applied": applied, "skipped": skipped}


def build_system_guard_prompt(evidence: dict, issues: list[dict]) -> str:
    payload = json.dumps(evidence or {}, ensure_ascii=False, separators=(",", ":"))
    issues_payload = json.dumps(issues or [], ensure_ascii=False, separators=(",", ":"))
    return (
        "Eres un revisor senior de fiabilidad para una plataforma SaaS de fútbol. "
        "No eres un asistente conversacional; actúas como una capa de control del sistema. "
        "Analiza SOLO la evidencia JSON y la lista de incidencias detectadas por el sistema. "
        "Debes detectar fallos actuales, riesgos probables, huecos de cobertura y priorizar reparación preventiva. "
        "No inventes endpoints ni checks no presentes en la evidencia. "
        "Devuelve SOLO JSON válido con estas claves exactas: "
        "overall_status:string, blockers:list, warnings:list, prevention_actions:list, watch_modules:list, autofix_candidates:list, summary:string. "
        "overall_status debe ser uno de: ok, watch, risk, fail. "
        "blockers/warnings/prevention_actions/watch_modules/autofix_candidates: máximo 6 elementos por lista. "
        "Cada prevention_action debe ser un objeto con {area, action, reason}. "
        "watch_modules debe listar {module, reason}. "
        "autofix_candidates debe listar {issue_id, why_now, safe_if_known}. "
        "Sé directo, técnico y en español.\n\n"
        f"EVIDENCE_JSON={payload}\nISSUES_JSON={issues_payload}"
    )


def _severity_rank(value: str) -> int:
    return {"info": 0, "warning": 1, "blocker": 2}.get(str(value or "").lower(), 0)


def _base_ok_from_issues(issues: list[dict]) -> bool:
    return not any(_severity_rank(issue.get("severity")) >= 2 for issue in (issues or []))


def run_system_guard(
    *,
    run_smoke: bool = False,
    smoke_verbosity: int = 1,
    run_llm: bool = True,
    auto_fix: bool = False,
) -> dict:
    initial_evidence = collect_system_guard_evidence(run_smoke=run_smoke, smoke_verbosity=smoke_verbosity)
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
            evidence = collect_system_guard_evidence(run_smoke=run_smoke, smoke_verbosity=smoke_verbosity)
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
        build_system_guard_prompt(evidence, issues),
        model=cfg.get("model"),
        base_url=cfg.get("base_url"),
        timeout=cfg.get("timeout"),
    )
    report["llm_review"]["available"] = isinstance(parsed, dict)
    report["llm_review"]["error"] = str(error or "")
    report["llm_review"]["review"] = parsed if isinstance(parsed, dict) else None
    return report
